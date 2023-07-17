! Created by Guillaume Monteil on 12/19/21.

module blh_mod

    use netcdf
    use com_mod, only : nx, ny, memind, hmix, ideltas, lsynctime, lconvection, ldirect
    implicit none
    private
    public :: write_blh

    !=================================================

    type t_ncdim
        integer :: lon, lat, time
    end type t_ncdim

    type(t_ncdim) :: ncdim

    character(len=120) :: blh_filename='blh.nc'

    integer :: itstep=1
    integer :: fid, vid

    contains

        subroutine write_blh(metdata_format)

            integer :: itime, metdata_format, nstop1

            call init_output_blh
            do itime=0,ideltas,lsynctime
                if ((ldirect.eq.-1).and.(lconvection.eq.1).and.(itime.lt.0)) then
                    call convmix(itime,metdata_format)
                endif
                call getfields(itime,nstop1,metdata_format)
                if (nstop1.gt.1) stop 'NO METEO FIELDS AVAILABLE'
                call output_blh
            end do
            call terminate_blh

        end subroutine write_blh

        subroutine init_output_blh
            ! Initialize netCDF file for output of boundary layer height
            !integer :: fid, vid

            ! Open the file
            call check(nf90_create(trim(blh_filename), NF90_NETCDF4, fid))

            ! Create spatial dimensions (fixed) + time dimension (unlimited)
            call check(nf90_def_dim(fid, 'lon', nx, ncdim%lon))
            call check(nf90_def_dim(fid, 'lat', ny, ncdim%lat))
            call check(nf90_def_dim(fid, 'time', NF90_UNLIMITED, ncdim%time))

            ! Create the blh variable
            ! Dimensions are passed in reverse order of the actual dimensions because the underlying C library uses different order convention than fortran
            call check(nf90_def_var(fid, 'blh', NF90_FLOAT, (/ ncdim%lon, ncdim%lat, ncdim%time /), vid))

            ! Close the file
            !call check(nf90_close(fid))

        end subroutine init_output_blh

        subroutine output_blh
            !integer :: vid, fid
            !call check(nf90_open(trim(blh_filename), NF90_NETCDF4, fid))
            !call check(nf90_inq_varid(fid, 'blh', vid))
            call check(nf90_put_var(fid, vid, hmix(0:nx-1, 0:ny-1, 1, memind(1)), (/1, 1, itstep/)))
            itstep = itstep + 1
            !call check(nf90_close(fid))
        end subroutine output_blh

        subroutine terminate_blh
            call check(nf90_close(fid))
        end subroutine terminate_blh

        subroutine check(status)
            integer, intent(in) :: status
            if (status .ne. nf90_noerr) then
                print*, trim(nf90_strerror(status))
                stop
            end if
        end subroutine check

end module blh_mod