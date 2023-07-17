module particles_mod

    use par_mod, only : dp

    type type_particles
        integer          :: number
        ! real(kind=dp)    :: x, y    ! horizontal position of the particle (xtra1, ytra1)
        ! real             :: z       ! vertical position of the particle (ztra1)
        integer          :: t       ! temporal position of the particle (itra1)
        integer          :: release ! release point of the particle (npoint)
        logical          :: active
        logical          :: free
        real, dimension(:), allocatable :: mass

        ! pointers (temporary ...)
        ! real, pointer             :: height
        ! real(kind=dp), pointer    :: x, y!, z
        real(kind=dp)    :: x, y
        real             :: z
        integer          :: release_time

        ! used for output only :
        real             :: lon, lat
        real             :: oro
        real             :: potential_vorticity
        real             :: specific_humidity
        real             :: density
        real             :: temperature
        real             :: pbl_height
        real             :: tropopause_height

        ! Methods
        contains
            procedure       :: interp_lon_lat
            procedure       :: interp_lon_lat_alt_time
            procedure       :: interp_lon_lat_time
            procedure       :: interp_lon_lat_alt
            procedure       :: update

    end type type_particles

    type(type_particles), dimension(:), allocatable, target :: particles

    type(type_particles), pointer :: pp


    contains


    subroutine init_particles(npart)
        use com_mod, only : ztra1

        integer, intent(in) :: npart

        allocate(particles(npart))

        particles%t = -999999999
        particles%free = .true.
        particles%active = .false.

    end subroutine init_particles


    subroutine update(self, itime)
        use com_mod, only : oro, pv, qv, rho, hmix, tropopause, tt
        class(type_particles) :: self
        integer, intent(in)   :: itime

        ! Check on the time and not on the "active" status (this way, particles that just got deactivated
        ! in this time step will be accounted for
        if ((itime == self%t)) then
            self%oro = self%interp_lon_lat(oro)
            self%potential_vorticity = self%interp_lon_lat_alt_time(pv, itime)
            self%specific_humidity = self%interp_lon_lat_alt_time(qv, itime)
            self%density = self%interp_lon_lat_alt_time(rho, itime)
            self%temperature = self%interp_lon_lat_alt_time(tt, itime)
            self%pbl_height = self%interp_lon_lat_time(hmix(:, :, 1, :), itime)
            self%tropopause_height = self%interp_lon_lat_time(tropopause(:, :, 1, :), itime)
        end if

    end subroutine update


    subroutine update_variables(itime)
        use com_mod, only : xlon0, dx, ylat0, dy, xtra1, ytra1, numpart, ztra1

        integer, intent(in) :: itime

        ! The following fields need to be calculated, when the particle is synchronized with the model
        do ipart = 1, numpart
            pp => particles(ipart)
            if (.not. pp%free) then
                pp%lon = xlon0 + xtra1(ipart) * dx
                pp%lat = ylat0 + ytra1(ipart) * dy
                pp%x = xtra1(ipart)
                pp%y = ytra1(ipart)
                pp%z = ztra1(ipart)
                call pp%update(itime)
            end if
            nullify(pp)
        end do

    end subroutine update_variables


    function interp_lon_lat(self, field) result (value)
        class(type_particles), intent(in)   :: self
        real, dimension(0:, 0:), intent(in) :: field
        real                                :: value

        real    :: dlon, dlat
        integer :: ilon1, ilat1, ilon2, ilat2

        ilon1 = int(self%x)
        ilat1 = int(self%y)
        ilon2 = ilon1 + 1
        ilat2 = ilat1 + 1
        if (ilon1 < 0) ilon1 = ilon2
        if (ilat1 < 0) ilat1 = ilat2
        if (ilon2 > nx - 1) ilon2 = ilon1
        if (ilat2 > ny - 1) ilat2 = ilat1

        dlon = self%x - ilon
        dlat = self%y - ilat

        value = (1 - dlon) * (1 - dlat) * field(ilon, ilat) &
                + dlon * (1 - dlat) * field(ilon + 1, ilat) &
                + (1 - dlon) * dlat * field(ilon, ilat + 1) &
                + dlon * dlat * field(ilon + 1, ilat + 1)

    end function interp_lon_lat


    function interp_lon_lat_alt(self, field) result (value)
        use com_mod, only : height

        class(type_particles), intent(in)       :: self
        real, dimension(0:, 0:, :), intent(in)  :: field
        real    :: value
        real    :: v1, v2
        real    :: z1, z2
        integer :: ilev

        ilev = findloc(height > self%z, .true., dim=1) - 1
        dz1 = self%z - height(ilev)
        dz2 = height(ilev + 1) - self%z

        v1 = self%interp_lon_lat(field(:, :, ilev))
        v2 = self%interp_lon_lat(field(:, :, ilev+1))

        value = (v1 * dz2 + v2 * dz1) / (dz1 + dz2)

    end function interp_lon_lat_alt


    function interp_lon_lat_alt_time(self, field, itime) result (value)
        use com_mod, only : memtime

        class(type_particles), intent(in)         :: self
        real, dimension(0:, 0:, :, :), intent(in) :: field
        integer, intent(in)                       :: itime
        real    :: value
        integer :: mem
        real    :: v1, v2
        real    :: dt1, dt2

        if (self%t == itime) then
            dt1 = real(self%t - memtime(1))
            dt2 = real(memtime(2) - self%t)

            v1 = self%interp_lon_lat_alt(field(:, :, :, 1))
            v2 = self%interp_lon_lat_alt(field(:, :, :, 2))
            value = (v1 * dt2 + v2 * dt1) / (dt1 + dt2)
        else
            ! return NaN
            value = 0
            value = 0 / value
        end if

    end function interp_lon_lat_alt_time


    function interp_lon_lat_time(self, field, itime) result (value)
        use com_mod, only : memtime

        class(type_particles), intent(in)         :: self
        real, dimension(0:, 0:, :), intent(in)    :: field
        integer, intent(in)                       :: itime
        real    :: value
        integer :: mem
        real    :: v1, v2
        real    :: dt1, dt2

        if (self%t == itime) then
            dt1 = real(self%t - memtime(1))
            dt2 = real(memtime(2) - self%t)

            v1 = self%interp_lon_lat(field(:, :, 1))
            v2 = self%interp_lon_lat(field(:, :, 2))
            value = (v1 * dt2 + v2 * dt1) / (dt1 + dt2)
        else
            ! return NaN
            value = 0
            value = 0 / value
        end if

    end function interp_lon_lat_time


end module particles_mod
