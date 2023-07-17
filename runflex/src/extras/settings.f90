module settings

    use go_rc,           only : trcfile, init, done, readrc

    implicit none

    private

    public :: config, read_config

    type settings_dict
        logical              :: userc=.false.   ! default is still to not use a rcfile
        logical              :: blh=.false.     ! default is not to compute blh
        logical              :: transport=.true.! transport of particles can be disabled if we only want to compute blh
    end type settings_dict

    type(trcfile) :: rcf

    type(settings_dict) :: config

    contains

        subroutine read_config(fname)
            character(len=*), intent(in) :: fname
            integer :: status

            call rcfile_init(fname, config%userc)

            if (config%userc) then
                call readrc(rcf, 'compute.blh', config%blh, status, default=config%blh)
                call readrc(rcf, 'compute.transport', config%transport, status, default=config%transport)
            end if

            call Done(rcf, status)
        end subroutine read_config

        subroutine rcfile_init(fname, userc)
            character(len=*), intent(in)  :: fname
            logical, intent(out)          :: userc
            integer                       :: status

            inquire(file=trim(fname), exist=userc)
            if (userc) then
                call Init(rcf, fname, status)
            end if
        end subroutine rcfile_init

end module settings