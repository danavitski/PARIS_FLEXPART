!**********************************************************************
! Copyright 1998,1999,2000,2001,2002,2005,2007,2008,2009,2010         *
! Andreas Stohl, Petra Seibert, A. Frank, Gerhard Wotawa,             *
! Caroline Forster, Sabine Eckhardt, John Burkhart, Harald Sodemann   *
!                                                                     *
! This file is part of FLEXPART.                                      *
!                                                                     *
! FLEXPART is free software: you can redistribute it and/or modify    *
! it under the terms of the GNU General Public License as published by*
! the Free Software Foundation, either version 3 of the License, or   *
! (at your option) any later version.                                 *
!                                                                     *
! FLEXPART is distributed in the hope that it will be useful,         *
! but WITHOUT ANY WARRANTY; without even the implied warranty of      *
! MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the       *
! GNU General Public License for more details.                        *
!                                                                     *
! You should have received a copy of the GNU General Public License   *
! along with FLEXPART.  If not, see <http://www.gnu.org/licenses/>.   *
!**********************************************************************

program flexpart

    !*****************************************************************************
    !                                                                            *
    !     This is the Lagrangian Particle Dispersion Model FLEXPART.             *
    !     The main program manages the reading of model run specifications, etc. *
    !     All actual computing is done within subroutine timemanager.            *
    !                                                                            *
    !     Author: A. Stohl                                                       *
    !                                                                            *
    !     18 May 1996                                                            *
    !                                                                            *
    !*****************************************************************************
    ! Changes:                                                                   *
    !   Unified ECMWF and GFS builds                                             *
    !   Marian Harustak, 12.5.2017                                               *
    !     - Added detection of metdata format using gributils routines           *
    !     - Distinguished calls to ecmwf/gfs gridcheck versions based on         *
    !       detected metdata format                                              *
    !     - Passed metdata format down to timemanager                            *
    !*****************************************************************************
    !                                                                            *
    ! Variables:                                                                 *
    !                                                                            *
    ! Constants:                                                                 *
    !                                                                            *
    !*****************************************************************************

    use point_mod
    use par_mod
    use com_mod
    use conv_mod
    use random_mod,        only : gasdev1
    use class_gribfile
    use netcdf_output_mod, only : writeheader_netcdf
    use settings,          only : config, read_config, init_calendar
    use blh_mod,           only : write_blh
    use particles_mod,     only : init_particles

    implicit none

    integer            :: i,j,ix,jy,inest, iopt
    integer            :: idummy = -320
    character(len=256) :: inline_options  !pathfile, flexversion, arg2
    integer            :: metdata_format = GRIBFILE_CENTRE_UNKNOWN
    integer            :: detectformat

    ! Read the rc-file (if present!):
    call read_config('flexpart.rc')

    ! Generate a large number of random numbers
    !******************************************

    do i=1,maxrand-1,2
        call gasdev1(idummy,rannumb(i),rannumb(i+1))
    end do
    call gasdev1(idummy,rannumb(maxrand),rannumb(maxrand-1))


    ! FLEXPART version string
    flexversion_major = '10' ! Major version number, also used for species file names
    flexversion='Version '//trim(flexversion_major)//'.4 (2019-11-12)'
    verbosity=0

    ! Read the pathnames where input/output files are stored
    !*******************************************************

    inline_options='none'
    select case (iargc())
    case (2)
        call getarg(1,arg1)
        pathfile=arg1
        call getarg(2,arg2)
        inline_options=arg2
    case (1)
        call getarg(1,arg1)
        pathfile=arg1
        if (arg1(1:1).eq.'-') then
            write(pathfile,'(a11)') './pathnames'
            inline_options=arg1 
        endif
    case (0)
        write(pathfile,'(a11)') './pathnames'
    end select


    ! Ingest inline options
    !*******************************************************
    if (inline_options(1:1).eq.'-') then
        print*,'inline_options:',inline_options
        !verbose mode
        iopt=index(inline_options,'v') 
        if (iopt.gt.0) then
            verbosity=1
            !print*, iopt, inline_options(iopt+1:iopt+1)
            if  (trim(inline_options(iopt+1:iopt+1)).eq.'2') then
                print*, 'Verbose mode 2: display more detailed information during run'
                verbosity=2
            endif
        endif
        !debug mode 
        iopt=index(inline_options,'d')
        if (iopt.gt.0) then
            debug_mode=.true.
        endif
        if (trim(inline_options).eq.'-i') then
            print*, 'Info mode: provide detailed run specific information and stop'
            verbosity=1
            info_flag=1
        endif
        if (trim(inline_options).eq.'-i2') then
            print*, 'Info mode: provide more detailed run specific information and stop'
            verbosity=2
            info_flag=1
        endif
    endif

    call readpaths

    ! Read the user specifications for the current model run
    !*******************************************************

    call readcommand

    ! Initialize arrays in com_mod
    !*****************************
    call com_mod_allocate_part(maxpart)

    ! Read the age classes to be used
    !********************************
    call readageclasses

    ! Read, which wind fields are available within the modelling period
    !******************************************************************
    call readavailable

    ! Detect metdata format
    !**********************
    metdata_format = detectformat()
    if (metdata_format.eq.GRIBFILE_CENTRE_ECMWF) then
        print *,'ECMWF metdata detected'
    elseif (metdata_format.eq.GRIBFILE_CENTRE_NCEP) then
        print *,'NCEP metdata detected'
    else
        print *,'Unknown metdata format'
        stop
    endif

    ! If nested wind fields are used, allocate arrays
    !************************************************
    call com_mod_allocate_nests

    ! Read the model grid specifications,
    ! both for the mother domain and eventual nests
    !**********************************************
    if (metdata_format.eq.GRIBFILE_CENTRE_ECMWF) then
        call gridcheck_ecmwf
    else
        call gridcheck_gfs
    end if
    call gridcheck_nests

    ! Read the output grid specifications
    !************************************
    if (config%transport) then
        call readoutgrid
        if (nested_output.eq.1) then
            call readoutgrid_nest
        endif
    end if

    ! Read the receptor points for which extra concentrations are to be calculated
    !*****************************************************************************
    call readreceptors

    ! Read the physico-chemical species property table
    !*************************************************
    !SEC: now only needed SPECIES are read in readreleases.f
    !call readspecies

    ! Read the landuse inventory
    !***************************
    call readlanduse

    ! Assign fractional cover of landuse classes to each ECMWF grid point
    !********************************************************************
    call assignland

    ! Read the coordinates of the release locations
    !**********************************************
    if (config%transport) call readreleases

    ! Read and compute surface resistances to dry deposition of gases
    !****************************************************************
    call readdepo

    ! Convert the release point coordinates from geografical to grid coordinates
    !***************************************************************************
    if (config%transport) call coordtrafo

    ! Initialize all particles to non-existent
    !*****************************************
    call init_particles(maxpart)

    ! For continuation of previous run, read in particle positions
    !*************************************************************
    if (ipin.eq.1) then
        call readpartpositions
    else
        numpart=0
        numparticlecount=0
    endif

    ! Calculate volume, surface area, etc., of all output grid cells
    ! Allocate fluxes and OHfield if necessary
    !***************************************************************
    call outgrid_init
    if (nested_output.eq.1) call outgrid_init_nest

    ! Read the OH field
    !******************
    if (OHREA .eqv. .TRUE.) call readOHfield

    ! Write basic information on the simulation to a file "header"
    ! and open files that are to be kept open throughout the simulation
    !******************************************************************

    call writeheader_netcdf(lnest=.false.)
    if (nested_output.eq.1) call writeheader_netcdf(lnest=.true.)

    call writeheader
    ! FLEXPART 9.2 ticket ?? write header in ASCII format 
    call writeheader_txt
    !if (nested_output.eq.1) call writeheader_nest
    if (nested_output.eq.1.and.surf_only.ne.1) call writeheader_nest
    if (nested_output.eq.1.and.surf_only.eq.1) call writeheader_nest_surf
    if (nested_output.ne.1.and.surf_only.eq.1) call writeheader_surf

    !open(unitdates,file=path(2)(1:length(2))//'dates')

    call openreceptors
    if ((iout.eq.4).or.(iout.eq.5)) call openouttraj

    ! Releases can only start and end at discrete times (multiples of lsynctime)
    !***************************************************************************
    do i=1,numpoint
        ireleasestart(i)=nint(real(ireleasestart(i))/real(lsynctime))*lsynctime
        ireleaseend(i)=nint(real(ireleaseend(i))/real(lsynctime))*lsynctime
    end do

    ! Initialize cloud-base mass fluxes for the convection scheme
    !************************************************************

    do jy=0,nymin1
        do ix=0,nxmin1
            cbaseflux(ix,jy)=0.
        end do
    end do
    do inest=1,numbnests
        do jy=0,nyn(inest)-1
            do ix=0,nxn(inest)-1
                cbasefluxn(ix,jy,inest)=0.
            end do
        end do
    end do

    ! Inform whether output kernel is used or not
    !*********************************************
    if (lroot) then
        if (.not.lusekerneloutput) then
            write(*,*) "Concentrations are calculated without using kernel"
        else
            write(*,*) "Concentrations are calculated using kernel"
        end if
    end if

    ! Simulation start/end
    call init_calendar

    ! Calculate particle trajectories
    !********************************
    if (config%transport) then
        call timemanager(metdata_format)
    else if (config%blh) then
        call write_blh(metdata_format)
    end if

    open(unit=321, file=trim(path(2)(1:length(2)))//'/flexpart.ok', status='new')

end program flexpart
