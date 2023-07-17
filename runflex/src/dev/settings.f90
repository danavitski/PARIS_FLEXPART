module settings

    use go_rc,           only : trcfile, init, done, readrc
    use datetime_module, only : datetime

    implicit none

    private

    public :: config, read_config, init_calendar

    type settings_dict
        logical              :: userc=.false.   ! default is still to not use a rcfile
        logical              :: blh=.false.     ! default is not to compute blh
        logical              :: transport=.true.! transport of particles can be disabled if we only want to compute blh
        type(datetime)       :: start, end
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

        ! Ensure that we can access the start/end dates of the simulation as datetimes
        function dateints_to_datetime(idate, itime) result (dtime)
            integer, intent(in) :: idate, itime
            type(datetime)      :: dtime
            integer :: year, month, day, hours, minutes, seconds, remainer

            year = int(idate / 10000.)
            remainer = idate - year * 10000
            month = int(remainer / 100.)
            remainer = remainer - month * 100
            day = int(remainer)

            hours = int(itime / 10000.)
            remainer = itime - hours * 10000
            minutes = int(remainer / 100.)
            remainer = remainer - minutes * 100
            seconds = int(remainer)

            dtime = datetime(year, month, day, hours, minutes, seconds)
        end function dateints_to_datetime

        subroutine init_calendar

            use com_mod, only : ibdate, iedate, ibtime, ietime, ldirect

            integer :: start_time, start_date, end_time, end_date

            ! Convert ietime, iedate / ibtime, ibdate to datetimes
            if (ldirect == -1) then
                config%start = dateints_to_datetime(iedate, ietime)
                config%end = dateints_to_datetime(ibdate, ibtime)
            else
                config%end = dateints_to_datetime(iedate, ietime)
                config%start = dateints_to_datetime(ibdate, ibtime)
            end if

        end subroutine init_calendar

end module settings