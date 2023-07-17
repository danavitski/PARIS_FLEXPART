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

subroutine timemanager(metdata_format)

    !*****************************************************************************
    !                                                                            *
    ! Handles the computation of trajectories, i.e. determines which             *
    ! trajectories have to be computed at what time.                             *
    ! Manages dry+wet deposition routines, radioactive decay and the computation *
    ! of concentrations.                                                         *
    !                                                                            *
    !     Author: A. Stohl                                                       *
    !                                                                            *
    !     20 May 1996                                                            *
    !                                                                            *
    !*****************************************************************************
    !  Changes, Bernd C. Krueger, Feb. 2001:                                     *
    !        Call of convmix when new windfield is read                          *
    !------------------------------------                                        *
    !  Changes Petra Seibert, Sept 2002                                          *
    !     fix wet scavenging problem                                             *
    !     Code may not be correct for decay of deposition!                       *
    !  Changes Petra Seibert, Nov 2002                                           *
    !     call convection BEFORE new fields are read in BWD mode                 *
    !  Changes Caroline Forster, Feb 2005                                        *
    !   new interface between flexpart and convection scheme                     *
    !   Emanuel's latest subroutine convect43c.f is used                         *
    !  Changes Stefan Henne, Harald Sodemann, 2013-2014                          *
    !   added netcdf output code                                                 *
    !  Changes Espen Sollum 2014                                                 *
    !   For compatibility with MPI version,                                      *
    !   variables uap,ucp,uzp,us,vs,ws,cbt now in module com_mod                 *
    !  Unified ECMWF and GFS builds                                              *
    !   Marian Harustak, 12.5.2017                                               *
    !   - Added passing of metdata_format as it was needed by called routines    *
    !*****************************************************************************
    !                                                                            *
    ! Variables:                                                                 *
    ! DEP                .true. if either wet or dry deposition is switched on   *
    ! decay(maxspec) [1/s] decay constant for radioactive decay                  *
    ! DRYDEP             .true. if dry deposition is switched on                 *
    ! ideltas [s]        modelling period                                        *
    ! itime [s]          actual temporal position of calculation                 *
    ! ldeltat [s]        time since computation of radioact. decay of depositions*
    ! loutaver [s]       averaging period for concentration calculations         *
    ! loutend [s]        end of averaging for concentration calculations         *
    ! loutnext [s]       next time at which output fields shall be centered      *
    ! loutsample [s]     sampling interval for averaging of concentrations       *
    ! loutstart [s]      start of averaging for concentration calculations       *
    ! loutstep [s]       time interval for which concentrations shall be         *
    !                    calculated                                              *
    ! npoint(maxpart)    index, which starting point the trajectory has          *
    !                    starting positions of trajectories                      *
    ! nstop              serves as indicator for fate of particles               *
    !                    in the particle loop                                    *
    ! nstop1             serves as indicator for wind fields (see getfields)     *
    ! outnum             number of samples for each concentration calculation    *
    ! outnum             number of samples for each concentration calculation    *
    ! prob               probability of absorption at ground due to dry          *
    !                    deposition                                              *
    ! WETDEP             .true. if wet deposition is switched on                 *
    ! weight             weight for each concentration sample (1/2 or 1)         *
    ! uap(maxpart),ucp(maxpart),uzp(maxpart) = random velocities due to          *
    !                    turbulence                                              *
    ! us(maxpart),vs(maxpart),ws(maxpart) = random velocities due to inter-      *
    !                    polation                                                *
    ! xtra1(maxpart), ytra1(maxpart), ztra1(maxpart) =                           *
    !                    spatial positions of trajectories                       *
    ! metdata_format     format of metdata (ecmwf/gfs)                           *
    !                                                                            *
    ! Constants:                                                                 *
    ! maxpart            maximum number of trajectories                          *
    !                                                                            *
    !*****************************************************************************

    use unc_mod
    use point_mod
    use xmass_mod
    use flux_mod
    use outg_mod
    use oh_mod
    use par_mod
    use com_mod

    use particles_mod,     only : particles, pp, update_variables
    use output_mod,        only : output_particles_final_position
    use netcdf_output_mod, only : concoutput_netcdf, concoutput_nest_netcdf, concoutput_surf_netcdf, concoutput_surf_nest_netcdf

    implicit none

    integer :: metdata_format
    integer :: j, ks, kp, l, n, itime = 0, nstop, nstop1
    integer :: loutnext, loutstart, loutend
    integer :: ix, jy, ldeltat, itage, nage, idummy
    integer :: i_nan = 0, ii_nan, total_nan_intl = 0  !added by mc to check instability in CBL scheme
    real :: outnum, weight, prob_rec(maxspec), prob(maxspec), decfact, wetscav
    real(sp) :: gridtotalunc
    real(dep_prec) :: drydeposit(maxspec), wetgridtotalunc, drygridtotalunc
    real :: xold, yold, zold, xmassfract
    real :: grfraction(3)
    real, parameter :: e_inv = 1.0 / exp(1.0)


    ! First output for time 0
    !************************

    loutnext = loutstep / 2
    outnum = 0.
    loutstart = loutnext - loutaver / 2
    loutend = loutnext + loutaver / 2

    !**********************************************************************
    ! Loop over the whole modelling period in time steps of mintime seconds
    !**********************************************************************


    if (.not.lusekerneloutput) write(*,*) 'Not using the kernel'
    if (turboff) write(*,*) 'Turbulence switched off'

    write(*,46) float(itime)/3600,itime,numpart

    do itime = 0, ideltas, lsynctime


        ! Computation of wet deposition, OH reaction and mass transfer
        ! between two species every lsynctime seconds
        ! maybe wet depo frequency can be relaxed later but better be on safe side
        ! wetdepo must be called BEFORE new fields are read in but should not
        ! be called in the very beginning before any fields are loaded, or
        ! before particles are in the system
        ! Code may not be correct for decay of deposition
        ! changed by Petra Seibert 9/02
        !********************************************************************

        if ((itime /= 0) .and. (numpart > 0)) then
            if (WETDEP) call wetdepo(itime, lsynctime, loutnext)
            if (OHREA) call ohreaction(itime, lsynctime, loutnext)
            if (ASSSPEC) stop 'associated species not yet implemented!'
        end if

        ! compute convection for backward runs
        !*************************************
	    if ((ldirect == -1) .and. (lconvection == 1) .and. (itime < 0)) then
            call convmix(itime, metdata_format)
        endif


        ! Get necessary wind fields if not available
        !*******************************************
        call getfields(itime, nstop1, metdata_format)
        if (nstop1 > 1) stop 'NO METEO FIELDS AVAILABLE'

        ! Get hourly OH fields if not available
        !****************************************************
        if (OHREA) call gethourlyOH(itime)

        ! Release particles
        !******************

        if (mdomainfill > 1) then
            if (itime == 0) then
                call init_domainfill
            else
                call boundcond_domainfill(itime, loutend)
            endif
        else
            call releaseparticles(itime)
        endif


        ! Compute convective mixing for forward runs
        ! for backward runs it is done before next windfield is read in
        !**************************************************************

        if ((ldirect == 1) .and. (lconvection == 1)) call convmix(itime, metdata_format)

        ! If middle of averaging period of output fields is reached, accumulated
        ! deposited mass radioactively decays
        !***********************************************************************

        if (DEP .and. (itime == loutnext) .and. (ldirect > 0)) then
            do ks=1, nspec
                do kp=1, maxpointspec_act
                    if (decay(ks) > 0) then
                        ! Mother output grid
			            wetgridunc(:, :, ks, kp, :, :) = wetgridunc(:, :, ks, kp, :, :) * exp(-outstep * decay(ks))
			            drygridunc(:, :, ks, kp, :, :) = drygridunc(:, :, ks, kp, :, :) * exp(-outstep * decay(ks))
                        if (nested_output == 1) then
                            wetgriduncn(:, :, ks, kp, :, :) = wetgriduncn(:, :, ks, kp, :, :) * exp(-outstep * decay(ks))
                            drygriduncn(:, :, ks, kp, :, :) = drygriduncn(:, :, ks, kp, :, :) * exp(-outstep * decay(ks))
                        endif
                    endif
                end do
            end do
        endif
        ! Check whether concentrations are to be calculated
        !**************************************************

        if ((ldirect * itime >= ldirect * loutstart) .and. (ldirect * itime <= ldirect * loutend)) then ! add to grid
            if (mod(itime - loutstart, loutsample) == 0) then

                ! If we are exactly at the start or end of the concentration averaging interval,
                ! give only half the weight to this sample
                !*****************************************************************************

                if ((itime == loutstart) .or. (itime == loutend)) then
                    weight = 0.5
                else
                    weight = 1.0
                endif
                outnum = outnum + weight
                call conccalc(itime, weight)
            endif


            if ((mquasilag == 1) .and. (itime == (loutstart + loutend) / 2)) call partoutput_short(itime)    ! dump particle positions in extremely compressed format


            ! Output and reinitialization of grid
            ! If necessary, first sample of new grid is also taken
            !*****************************************************

            if ((itime == loutend) .and. (outnum > 0.)) then
                if ((iout <= 3.) .or. (iout == 5)) then
                    if (surf_only /= 1) then 
                        if (lnetcdfout == 1) then 
                            call concoutput_netcdf(itime, outnum, gridtotalunc, wetgridtotalunc, drygridtotalunc)
                        else 
                            call concoutput(itime, outnum, gridtotalunc, wetgridtotalunc, drygridtotalunc)
                        endif
                    else  
                        if (lnetcdfout == 1) then
                            call concoutput_surf_netcdf(itime, outnum, gridtotalunc, wetgridtotalunc, drygridtotalunc)
                        else
                            if (linversionout == 1) then
                                call concoutput_inversion(itime, outnum, gridtotalunc, wetgridtotalunc, drygridtotalunc)
                            else
                                call concoutput_surf(itime, outnum, gridtotalunc, wetgridtotalunc, drygridtotalunc)
                            endif
                        endif
                    endif

                    if (nested_output == 1) then
                        if (lnetcdfout == 0) then
                            if (surf_only /= 1) then
                                call concoutput_nest(itime, outnum)
                            else 
                                if (linversionout == 1) then
                                    call concoutput_inversion_nest(itime, outnum)
                                else 
                                    call concoutput_surf_nest(itime, outnum)
                                endif
                            endif
                        else
                            if (surf_only /= 1) then
                                call concoutput_nest_netcdf(itime, outnum)
                            else 
                                call concoutput_surf_nest_netcdf(itime, outnum)
                            endif
                        endif
                    endif
                    outnum = 0.
                endif

                if ((iout == 4) .or. (iout == 5)) call plumetraj(itime)
                if (iflux == 1) call fluxoutput(itime)
                write(*,45) itime,ideltas,numpart,gridtotalunc,wetgridtotalunc,drygridtotalunc

                45      format(i13,'/',i13,' Seconds simulated; ',i13, ' Particles;    Uncertainty: ',3f7.3)
                46      format(' Simulated ',f7.1,' hours (',i13,' s), ',i13, ' particles')
                if (ipout > 1) then
                    if (mod(itime, ipoutfac * loutstep) == 0) call partoutput(itime) ! dump particle positions
                    if (ipout == 3) call partoutput_average(itime) ! dump particle positions
                endif
                loutnext = loutnext + loutstep
                loutstart = loutnext - loutaver / 2
                loutend = loutnext + loutaver / 2
                if (itime == loutstart) then
                    weight = 0.5
                    outnum = outnum + weight
                    call conccalc(itime,weight)
                endif


                ! Check, whether particles are to be split:
                ! If so, create new particles and attribute all information from the old
                ! particles also to the new ones; old and new particles both get half the
                ! mass of the old ones
                !************************************************************************

                if (ldirect * itime >= ldirect * itsplit) then
                    n = numpart
                    do j = 1, numpart
                        if (ldirect * itime >= ldirect * itrasplit(j)) then
                            if (n < maxpart) then
                                n = n + 1
                                itrasplit(j) = 2 * (itrasplit(j) - itramem(j)) + itramem(j)
                                itrasplit(n) = itrasplit(j)
                                itramem(n) = itramem(j)
                                particles(n)%t = particles(j)%t
                                idt(n) = idt(j)
                                npoint(n) = npoint(j)
                                nclass(n) = nclass(j)
                                xtra1(n) = xtra1(j)
                                ytra1(n) = ytra1(j)
                                ztra1(n) = ztra1(j)
                                uap(n) = uap(j)
                                ucp(n) = ucp(j)
                                uzp(n) = uzp(j)
                                us(n) = us(j)
                                vs(n) = vs(j)
                                ws(n) = ws(j)
                                cbt(n) = cbt(j)
                                do ks = 1, nspec
                                    xmass1(j, ks) = xmass1(j, ks) / 2.
                                    xmass1(n, ks) = xmass1(j, ks)
                                end do
                            endif
                        endif
                    end do
                    numpart = n
                endif
            endif
        endif


        if (itime /= ideltas) then

            ! Compute interval since radioactive decay of deposited mass was computed
            !************************************************************************

            if (itime < loutnext) then
                ldeltat = itime - (loutnext - loutstep)
            else                                  ! first half of next interval
                ldeltat = itime - loutnext
            endif

            ! Loop over all particles
            !************************
            ! Various variables for testing reason of CBL scheme, by mc
            well_mixed_vector = 0. !erase vector to test well mixed condition: modified by mc
            well_mixed_norm = 0.   !erase normalization to test well mixed condition: modified by mc
            avg_ol = 0.
            avg_wst = 0.
            avg_h = 0.
            avg_air_dens = 0.  !erase vector to obtain air density at particle positions: modified by mc
            !-----------------------------------------------------------------------------
            do j = 1, numpart
                pp => particles(j)
                ! If integration step is due, do it
                !**********************************
                if (pp%active) then
                    if (ioutputforeachrelease == 1) then
                        kp = npoint(j)
                    else
                        kp = 1
                    endif
                    ! Determine age class of the particle
                    itage = abs(pp%t - itramem(j))
                    do nage = 1, nageclass
                        if (itage < lage(nage)) exit
                    end do

                    ! Initialize newly released particle
                    !***********************************
                    if ((itramem(j) == itime) .or. (itime == 0)) then
                        call initialize(itime, idt(j), uap(j), ucp(j), uzp(j), us(j), vs(j), ws(j), xtra1(j), ytra1(j), ztra1(j), cbt(j))
                    endif

                    ! Memorize particle positions
                    !****************************
                    xold = xtra1(j)
                    yold = ytra1(j)
                    zold = ztra1(j)

                    ! RECEPTOR: dry/wet depovel
                    !****************************
                    ! Before the particle is moved
                    ! the calculation of the scavenged mass shall only be done once after release
                    ! xscav_frac1 was initialised with a negative value
                    if  (DRYBKDEP) then
                        do ks = 1, nspec
                            if  ((xscav_frac1(j, ks) < 0)) then
                                call get_vdep_prob(itime, xtra1(j), ytra1(j), ztra1(j), prob_rec)
                                if (DRYDEPSPEC(ks)) then        ! dry deposition
                                    xscav_frac1(j, ks) = prob_rec(ks)
                                else
                                    xmass1(j, ks) = 0.
                                    xscav_frac1(j, ks) = 0.
                                endif
                            endif
                        enddo
                    endif

                    if (WETBKDEP) then
                        do ks = 1, nspec
                            if  ((xscav_frac1(j, ks) < 0)) then
                                call get_wetscav(itime, lsynctime, loutnext, j, ks, grfraction, idummy, idummy, wetscav)
                                if (wetscav > 0) then
                                    xscav_frac1(j, ks) = wetscav * (zpoint2(npoint(j)) - zpoint1(npoint(j))) * grfraction(1)
                                else
                                    xmass1(j, ks) = 0.
                                    xscav_frac1(j, ks) = 0.
                                endif
                            endif
                        enddo
                    endif

                    ! Integrate Lagevin equation for lsynctime seconds
                    !*************************************************

                    call advance(itime, npoint(j), idt(j), uap(j), ucp(j), uzp(j), us(j), vs(j), ws(j), nstop, xtra1(j), ytra1(j), ztra1(j), prob, cbt(j), j)
                    ! Calculate average position for particle dump output
                    !****************************************************

                    if (ipout  == 3) call partpos_average(itime, j)


                    ! Calculate the gross fluxes across layer interfaces
                    !***************************************************

                    if (iflux == 1) call calcfluxes(nage, j, xold, yold, zold)


                    ! Determine, when next time step is due
                    ! If trajectory is terminated, mark it
                    !**************************************
                    if (nstop > 1) then
                        if (linit_cond >= 1) call initial_cond_calc(itime, j)
                        pp%active = .false.
                    else
                        pp%t = itime + lsynctime

                        ! Dry deposition and radioactive decay for each species
                        ! Also check maximum (of all species) of initial mass remaining on the particle;
                        ! if it is below a threshold value, terminate particle
                        !*****************************************************************************
                        xmassfract = 0.
                        do ks = 1, nspec
                            if (decay(ks) > 0.) then             ! radioactive decay
                                decfact = exp(-real(abs(lsynctime)) * decay(ks))
                            else
                                decfact = 1.
                            endif

                            if (DRYDEPSPEC(ks)) then        ! dry deposition
                                drydeposit(ks) = xmass1(j, ks) * prob(ks) * decfact
                                xmass1(j, ks) = xmass1(j, ks) * (1. - prob(ks)) * decfact
                                if (decay(ks) > 0.) then   ! correct for decay (see wetdepo)
                                    drydeposit(ks) = drydeposit(ks) * exp(real(abs(ldeltat)) * decay(ks))
                                endif
                            else                           ! no dry deposition
                                xmass1(j, ks) = xmass1(j, ks) * decfact
                            endif

                            ! Skip check on mass fraction when npoint represents particle number
                            if ((mdomainfill == 0) .and. (mquasilag == 0)) then
                                if (xmass(npoint(j), ks) > 0.) then
                                    xmassfract = max(xmassfract, real(npart(npoint(j))) * xmass1(j, ks) / xmass(npoint(j), ks))
                                end if
                            else
                                xmassfract = 1.0
                            end if
                        end do

                        if (xmassfract < minmass) then   ! terminate all particles carrying less mass
                            pp%active = .false.
                        endif

                        !        Sabine Eckhardt, June 2008
                        !        don't create depofield for backward runs
                        if (DRYDEP .and. (ldirect == 1)) then
                            call drydepokernel(nclass(j), drydeposit, real(xtra1(j)), real(ytra1(j)), nage, kp)
                            if (nested_output == 1) call drydepokernel_nest(nclass(j), drydeposit, real(xtra1(j)), real(ytra1(j)), nage, kp)
                        endif

                        ! Terminate trajectories that are older than maximum allowed age
                        !***************************************************************

                        if (pp%t - itramem(j) >= lage(nageclass)) then
                            if (linit_cond >= 1) call initial_cond_calc(itime + lsynctime, j)
                            pp%active = .false.
                        endif
                    endif
                endif
                nullify(pp)
            end do !loop over particles



            ! Counter of "unstable" particle velocity during a time scale of
            ! maximumtl=20 minutes (defined in com_mod)
            !***************************************************************
            total_nan_intl = 0
            i_nan = i_nan + 1 ! added by mc to count nan during a time of maxtl (i.e. maximum tl fixed here to 20 minutes, see com_mod)
            sum_nan_count(i_nan) = nan_count
            if (i_nan > maxtl / lsynctime) i_nan = 1 !lsynctime must be <= maxtl
            do ii_nan = 1, (maxtl / lsynctime)
                total_nan_intl = total_nan_intl + sum_nan_count(ii_nan)
            end do
            ! Output to keep track of the numerical instabilities in CBL simulation and if
            ! they are compromising the final result (or not)
        end if

        call update_variables(itime)

    end do

    call output_particles_final_position


    ! Complete the calculation of initial conditions for particles not yet terminated
    !*****************************************************************************

    do j = 1, numpart
        if (linit_cond >= 1) call initial_cond_calc(itime, j)
    end do

    if (ipout == 2) call partoutput(itime)     ! dump particle positions

    if (linit_cond >= 1) then
        if (linversionout == 1) then
            call initial_cond_output_inversion(itime)   ! dump initial cond. field
        else
            call initial_cond_output(itime)   ! dump initial cond. fielf
        endif
    endif

end subroutine timemanager

