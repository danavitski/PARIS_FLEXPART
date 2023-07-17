!###############################################################################
!
#define IF_ERROR_RETURN(action) if (status/=0) then; write (gol,'("in ",a)') rname; call goErr; action; return; end if
!
!###############################################################################


module GO_File

  implicit none

  ! --- in/out -------------------

  private

  public  ::  goGetFU

  public  ::  TTextFile
  public  ::  Init, Done
  public  ::  ReadLine, RewindFile


  ! --- const ---------------------------------

  character(len=*), parameter  ::  mname = 'GO_File'


  ! --- types -------------------------------------

  type TTextFile
    character(len=80)       ::  name
    ! file unit:
    integer                 ::  fu
    ! comment ?
    logical                 ::  commented
    character(len=1)        ::  comment
  end type TTextFile


  ! --- interfaces -------------------------------------

  interface Init
    module procedure file_Init
  end interface

  interface Done
    module procedure file_Done
  end interface


contains


  ! ==============================================================
  ! ===
  ! === file units
  ! ===
  ! ==============================================================


  ! Returns the first free available file unit number.

  subroutine goGetFU( fu, status )

    use GO_FU   , only : goStdIn, goStdOut, goStdErr
    use GO_FU   , only : goFuRange
    use GO_Print, only : gol, goErr
    use os_specs, only : MAX_FILENAME_LEN

    ! --- in/out --------------------------

    integer, intent(out)      ::  fu
    integer, intent(out)      ::  status

    ! --- const ---------------------------

    character(len=*), parameter  ::  rname = mname//'/goGetFU'

    ! --- local --------------------------

    integer               ::  i
    character(len=MAX_FILENAME_LEN)    ::  fname
    logical               ::  opened

    ! --- local ---------------------------

    ! start with lowest possible unit:
    fu = goFuRange(1) - 1

    ! loop until unopned unit is found:
    do

      ! try next file unit:
      fu = fu + 1

      ! too large ?
      if ( fu > goFuRange(2) ) then
        write (gol,'("unable to select free file unit within allowed range ...")'); call goErr
        write (gol,'("close some files or increase goFuRange in module GO_FU")'); call goErr
        write (gol,'("current goFuRange : ",i6," .. ",i6)') goFuRange; call goErr
        write (gol,'("open files:")')
        do i = goFuRange(1), goFuRange(2)
          inquire( unit=i, name=fname )
          write (gol,'(i6," : ",a)') i, trim(fname); call goErr
        end do
        write (gol,'("in ",a)') rname; call goErr; status=1; return
      end if

      ! skip ?
      if ( fu==goStdIn  ) cycle
      if ( fu==goStdOut ) cycle
      if ( fu==goStdErr ) cycle

      ! free available unit ? then ok
      inquire( unit=fu, opened=opened )
      if ( .not. opened ) exit

    end do

    ! ok
    status = 0

  end subroutine goGetFU


  ! ==============================================================
  ! ===
  ! === text file
  ! ===
  ! ==============================================================


  !
  ! call Init( file, filename, iostat, [,status='unknown'|'old'|'new'] [,comment='\%'] )
  !
  ! Replaces the intrinsic 'open' command, but uses a
  ! a structure of type TTextFile instead of a file unit number. \\
  ! Arguments passed are the same as for 'open'.\\
  ! In addition, a text file can be opened as a commented
  ! text file; with the 'ReadLine' command one is able to read
  ! lines from the file while skipping the lines starting
  ! with the specified comment.
  !

  subroutine file_Init( file, filename, iostat, status, comment )

    use GO_Print, only : gol, goPr, goErr

    ! --- in/out ------------------------

    type(TTextFile), intent(out)              ::  file
    character(len=*), intent(in)              ::  filename
    integer, intent(out)                      ::  iostat

    character(len=*), intent(in), optional    ::  status
    character(len=1), intent(in), optional    ::  comment

    ! --- const ---------------------------

    character(len=*), parameter  ::  rname = mname//'/file_Init'

    ! --- local ----------------------------

    logical             ::  exist
    character(len=10)   ::  statusX

    ! --- begin ----------------------------

    ! file exist ?
    inquire( file=trim(filename), exist=exist )
    if ( .not. exist ) then
      write (gol,'("commented text file not found:")'); call goErr
      write (gol,'("  file name : ",a)') trim(filename); call goErr
      write (gol,'("in ",a)') rname; call goErr; iostat=1; return
    end if

    ! check file status : 'old', 'new', 'unknown'
    if (present(status)) then
      statusX = status
    else
      statusX = 'unknown'
    end if

    ! store filename:
    file%name = filename

    ! select free file unit:
    Call goGetFU( file%fu, iostat )
    if (iostat/=0) then; write (gol,'("in ",a)') rname; call goErr; iostat=1; return; end if

    ! open file:
    open( unit=file%fu, file=trim(filename), iostat=iostat, &
                                 status=statusX, form='formatted' )
    if ( iostat /= 0 ) then
      write (gol,'("from file open :")'); call goErr
      write (gol,'("  file name : ",a)') trim(filename); call goErr
      write (gol,'("in ",a)') rname; call goErr; iostat=1; return
    end if

    ! check on comment lines ?
    if ( present(comment) ) then
      file%commented = .true.
      file%comment = comment
    else
      file%commented = .false.
      file%comment = 'x'
    end if

    ! ok
    iostat = 0

  end subroutine file_Init


  ! ***


  !
  ! call Done( file )
  !

  subroutine file_Done( file, status )

    use GO_Print, only : gol, goPr, goErr

    ! --- in/out -----------------

    type(TTextFile), intent(inout)    ::  file
    integer, intent(out)              ::  status

    ! --- const ----------------------

    character(len=*), parameter  ::  rname = mname//'/file_Done'

    ! --- begin ------------------------

    ! close file:
    close( unit=file%fu, iostat=status )
    if ( status /= 0 ) then
      write (gol,'("from closing file:")'); call goErr
      write (gol,'("  ",a)') trim(file%name); call goErr
      write (gol,'("in ",a)') rname; call goErr; status=1; return
    end if

    ! ok
    status = 0

  end subroutine file_Done


  ! ***


  !
  ! call ReadLine( file, s )
  !
  ! Reads the next line from a commented text file,
  ! but skips all lines starting with the 'comment'
  ! specified with the 'Init' command.
  ! Empty lines are skipped too.
  !

  subroutine ReadLine( file, s, status  )

    use GO_Print, only : gol, goPr, goErr

    ! --- in/out -------------------------

    type(TTextFile), intent(inout)      ::  file
    character(len=*), intent(out)       ::  s
    integer, intent(out)                ::  status

    ! --- const --------------------------

    character(len=*), parameter  ::  rname = mname//'/ReadLine'

    ! --- local --------------------------

    character(len=10)        ::  fmt

    ! --- begin --------------------------

    ! format (a100) etc:
    write (fmt,'("(a",i6.6,")")') len(s)

    ! loop until:
    !  o uncommented line has been read in s
    !  o eof is reached
    do

      ! read next line:
      read (file%fu,fmt,iostat=status) s
      if ( status < 0 ) then  ! eof
        s = ''
        status=-1; return
      else if ( status > 0 ) then
        write (gol,'("reading line from file:")'); call goErr
        write (gol,'("  ",a)') trim(file%name); call goErr
        write (gol,'("in ",a)') rname; call goErr; status=1; return
      end if

      ! remove leading space:
      s = adjustl( s )

      ! empty ?
      if ( len_trim(s) == 0 ) cycle

      ! check for comment ?
      if ( file%commented .and. (scan(s,file%comment)==1) ) cycle

      ! s filled; leave loop
      exit

    end do

    ! ok
    status = 0

  end subroutine ReadLine

  subroutine RewindFile( file, status)

    use GO_Print, only : gol, goPr, goErr

    ! --- in/out -------------------------

    type(TTextFile), intent(inout)      ::  file
    integer, intent(out)                ::  status

    ! --- const --------------------------

    character(len=*), parameter  ::  rname = mname//'/RewindFile'

    ! --- local --------------------------

    ! --- begin --------------------------

    rewind(unit = file%fu, iostat = status)
    if (status /= 0 ) then
        write (gol,'("Rewind operation failed")')    ; call goErr
        write (gol,*) 'On file: ',trim(file%name)    ; call goErr
        write (gol,*) 'Unit   : ',file%fu            ; call goErr
        write (gol,'("in ",a)') rname; call goErr; status=1; return
    endif
    status = 0

  end subroutine RewindFile

end module GO_File


! ###########################################################################
! ###
! ### test program
! ###
! ###########################################################################
!
! ---[test.rc]--------------------------------------
! !
! ! abcdefg
! ! 2
!
! 0000000001111111111222222222233333333334
! 1234567890123456789012345678901234567890
!
! aaa :     kasfjasfjsla;kfja;ls
!
!   !  xxxxxxxxxx
!
!       bbb  : 123
! --------------------------------------------------
!
!program test_go_file
!
!  use go_file
!
!  type(TTextFile)     ::  file
!  character(len=25)  ::  s
!  integer             ::  status
!
!  call Init( file, 'test.rc', status )
!  if (status/=0) stop 'error'
!
!  do
!
!    call ReadLine( file, s, status )
!    if (status<0) then
!      print *, 'xxx eof'
!      exit
!    else if ( status == 0 ) then
!      print *, 'xxx "'//trim(s)//'"'
!    else
!      print *, 'xxx error'
!      exit
!    end if
!
!  end do
!
!  call Done( file, status )
!  if (status/=0) stop 'error'
!
!
!end program test_go_file
!
