module netcdf_tools

    use netcdf

    implicit none

    contains

    subroutine nf90_err(status)
        ! Copied from netcdf_output_mod, but made available to other modules as well
        integer, intent (in) :: status
        if(status /= nf90_noerr) then
            print *, trim(nf90_strerror(status))
            stop 'Stopped'
        end if
    end subroutine nf90_err

end module netcdf_tools