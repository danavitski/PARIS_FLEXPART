module output_mod

    use netcdf
    use netcdf_tools,  only : nf90_err
    use particles_mod, only : particles, pp, type_particles

    implicit none

    contains

    subroutine output_particles_final_position

        use com_mod,   only : numpart, path, compoint, numpoint, npoint
        use point_mod, only : npart
        use settings,  only : config

        ! NetCDF variables:
        integer             :: ncstat
        integer             :: fid, dimid, varid, grpid

        ! Regular variables
        character(len=200)  :: filename
        logical, dimension(:), allocatable    :: filter
        integer                               :: irl
        integer(1), dimension(:), allocatable :: dummy

        type(type_particles), dimension(:), allocatable :: parts

        ! Write the position of the particles at the end of their life (or when the simulation ends).
        write(filename, *) trim(path(2))//'particles_final.nc'

        ! Open file
        ncstat = nf90_create(trim(filename), NF90_NETCDF4, fid)

        ! Loop over the releases:
        do irl = 1, numpoint
            print*, compoint(irl)

            call nf90_err(nf90_def_grp(fid, trim(compoint(irl)), grpid))

            ! Dimension: number of particles in that release
            call nf90_err(nf90_def_dim(grpid, 'particles', npart(irl), dimid))

            filter = npoint == irl
            parts = pack(particles, npoint == irl)

            call nf90_err(nf90_def_var(grpid, 'lon', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%lon))

            call nf90_err(nf90_def_var(grpid, 'lat', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%lat))

            call nf90_err(nf90_def_var(grpid, 'height', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%z))

            call nf90_err(nf90_def_var(grpid, 'surface_height', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%oro))

            call nf90_err(nf90_def_var(grpid, 'potential_vorticity', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%potential_vorticity))

            call nf90_err(nf90_def_var(grpid, 'specific_humidity', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%specific_humidity))

            call nf90_err(nf90_def_var(grpid, 'air_density', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%density))

            call nf90_err(nf90_def_var(grpid, 'pbl_height', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%pbl_height))

            call nf90_err(nf90_def_var(grpid, 'tropopause_height', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%tropopause_height))

            call nf90_err(nf90_def_var(grpid, 'temperature', nf90_float, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%temperature))

            !call nf90_err(nf90_def_var(fid, 'mass', nf90_float, (/dimid/), varid))
            !call nf90_err(nf90_put_var(fid, varid, particles%mass))

            call nf90_err(nf90_def_var(grpid, 'release_time', nf90_int, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%release_time))

            call nf90_err(nf90_def_var(grpid, 'time', nf90_int, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, parts%t))
            call nf90_err(nf90_put_att(grpid, varid, 'units', config%start%strftime('seconds since %Y-%m-%d %H:%M:%S')))
            call nf90_err(nf90_put_att(grpid, varid, 'calendar', 'proleptic_gregorian'))

!            call nf90_err(nf90_def_var(grpid, 'id', nf90_int, (/dimid/), varid))
!            call nf90_err(nf90_put_var(grpid, varid, )

            ! ng90_def_var doesn't seem to support logical arrays directly, so we convert them to integer(1) arrays
            ! the "nf90_byte" type ensures that we get logicals in the file anyway/

            allocate(dummy(10000))
            dummy(:) = parts%active
            call nf90_err(nf90_def_var(grpid, 'active', nf90_byte, (/dimid/), varid))
            call nf90_err(nf90_put_var(grpid, varid, dummy))

!            dummy(:) = parts%free
!            call nf90_err(nf90_def_var(grpid, 'free', nf90_byte, (/dimid/), varid))
!            call nf90_err(nf90_put_var(grpid, varid, dummy))
            deallocate(dummy)

        end do

        call nf90_err(nf90_close(fid))

    end subroutine output_particles_final_position

end module output_mod