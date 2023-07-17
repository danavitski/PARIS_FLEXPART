!
! go print : tools for standard output
!
! Example:
!
!   ! initialise messages:
!   !  o printed by root only ;
!   !  o start each line with the processor number specified to 'pe' ;
!   !  o write messages to the specified file:
!   call GO_Print_Init( status, apply=myid==root, &
!                           prompt_pe=npes>1, pe=myid, &
!                           file=.true., file='my.out' )
!   if (status/=0) stop
!
!   ! write single message line; processor number is included:
!   !   [00] This is number  3
!   write (gol,'("This is number ",i2)') 3; call goPr
!
!   ! write error message:
!   !   [00] ERROR - Something wrong.
!   write (gol,'("Something wrong.")'); call goErr
!
!   ! write a debug message;
!   ! always written, even if 'apply' was set to .false. :
!   !   [00] BUG - take a look at this :      0
!   !   [01] BUG - take a look at this : -32567
!   write (gol,'("take a look at this : ",i6)') value; call goErr
!
!   ! done
!   call GO_Print_Done( status )
!   if (status/=0) stop
!

module GO_Print

  use os_specs, only : MAX_FILENAME_LEN

  implicit none

  ! --- in/out ---------------------------------

  private

  ! public for users:
  public  ::  gol
  public  ::  GO_Print_Init, GO_Print_Done
  public  ::  goPr, goErr, goBug

  ! GO internal routines:
  public  ::  GO_Print_Indent, GO_Print_DeIndent


  ! --- const ---------------------------------

  character(len=*), parameter  ::  mname = 'GO_Print'

  ! length of message line:
  integer, parameter  ::  len_gol = 1024

  ! --- var ------------------------------------

  ! buffer for standard output
  character(len=len_gol)  ::  gol

  ! initialized ?
  ! some errors might be printed before initialization ...
  logical              ::  pr_initialized = .false.

  ! destination file unit:
  integer              ::  pr_fu

  ! flags etc
  logical              ::  pr_apply

  ! processor prompt
  logical              ::  pr_prompt_pe
  integer              ::  pr_pe

  ! white space for indents:
  integer, parameter   ::  dindent = 2
  integer              ::  indent = 0

  ! writ to file ?
  logical              ::  pr_file
  character(len=MAX_FILENAME_LEN)   ::  pr_file_name


contains


  ! ***************************************************************************
  ! ***
  ! *** module init/done
  ! ***
  ! ***************************************************************************


  subroutine GO_Print_Init( status, apply, prompt_pe, pe, file, file_name )

    use go_fu, only : goStdOut

    ! --- in/out ----------------------------

    integer, intent(out)                     ::  status
    logical, intent(in), optional            ::  apply
    logical, intent(in), optional            ::  prompt_pe
    integer, intent(in), optional            ::  pe
    logical, intent(in), optional            ::  file
    character(len=*), intent(in), optional   ::  file_name

    ! --- const ----------------------------

    character(len=*), parameter  ::  rname = mname//'/GO_Print_Init'

    ! --- local -----------------------------

    logical   ::  opened

    ! --- begin -----------------------------

    ! print or not ?
    pr_apply = .true.
    if ( present(apply) ) pr_apply = apply

    ! processor number
    pr_pe = 0
    if ( present(pe) ) pr_pe = pe

    ! prompt processor number ?
    pr_prompt_pe = .false.
    if ( present(prompt_pe) ) pr_prompt_pe = prompt_pe

    ! write to file ?
    pr_file = .false.
    if ( present(file) ) pr_file = file
    pr_file_name = 'go.out'
    if ( present(file_name) ) pr_file_name = file_name

    ! no indent yet
    indent = 0

    ! write messages to file ?
    if ( pr_file ) then
      ! select free file unit:
      pr_fu = 10
      do
        inquire( pr_fu, opened=opened )
        if ( .not. opened ) exit
        pr_fu = pr_fu + 1
      end do
      ! open requested output file:
      open( unit=pr_fu, file=pr_file_name, status='replace', iostat=status )
      if ( status/=0 ) then
        write (*,'("ERROR - opening file for output:")')
        write (*,'("ERROR -   unit : ",i6)') pr_fu
        write (*,'("ERROR -   file : ",a)') trim(pr_file_name)
        write (*,'("ERROR in ",a)') rname; status=1; return
      end if
    else
      ! write to standard output:
      pr_fu = goStdOut
    end if

    ! now the module is initialized ...
    pr_initialized = .true.

    ! ok
    status = 0

  end subroutine GO_Print_Init


  ! ***


  subroutine GO_Print_Done( status )

    ! --- in/out ----------------------------

    integer, intent(out)           ::  status

    ! --- const ----------------------------

    character(len=*), parameter  ::  rname = mname//'/GO_Print_Done'

    ! --- begin -----------------------------

    ! output to file ?
    if ( pr_file ) then
      ! close file:
      close( pr_fu, iostat=status )
      if ( status/=0 ) then
        write (*,'("ERROR - closing output file:")')
        write (*,'("ERROR -   unit : ",i6)') pr_fu
        write (*,'("ERROR -   file : ",a)') trim(pr_file_name)
        write (*,'("ERROR in ",a)') rname; status=1; return
      end if
    end if


    ! ok
    status = 0

  end subroutine GO_Print_Done


  ! ***************************************************************************
  ! ***
  ! *** printing
  ! ***
  ! ***************************************************************************


  subroutine goPr

    ! --- local --------------------------------

    character(len=16)   ::  prompt, s
    integer             ::  nind

    ! --- const ----------------------------

    character(len=*), parameter  ::  rname = mname//'/goPr'

    ! --- begin --------------------------------

    ! not initialized yet ? then print to standard output:
    if ( .not. pr_initialized ) then
      write (*,'(a)') trim(gol)
      gol = ''
      return
    end if

    ! print go line ?
    if ( pr_apply ) then

      ! number of spaces to indent:
      nind = max( 0, indent )

      ! processor prompt ?
      if ( pr_prompt_pe ) then
        write (prompt,'("[",i2.2,"]")') pr_pe
        nind = nind + 1
      else
        prompt = ''
      end if

      ! write prompt, indention, go line:
      if ( nind > 0 ) then
        write (pr_fu,'(a,a,a)') trim(prompt), repeat(' ',nind), trim(gol)
      else
        write (pr_fu,'(a,a)') trim(prompt), trim(gol)
      end if

    end if

    ! clear output line:
    gol = ''

  end subroutine goPr


  ! ***

  ! Print error message.
  ! Now printed to standard output, in future to standard error ?

  subroutine goErr

    ! --- local -------------------------------

    integer     ::  ilab

    ! --- const ----------------------------

    character(len=*), parameter  ::  rname = mname//'/goErr'

    ! --- local ----------------------------

    logical                   ::  save_pr_apply
    character(len=len_gol)    ::  gol2

    ! --- begin --------------------------------

    ! store original apply flag:
    save_pr_apply = pr_apply
    ! always print error messages:
    pr_apply = .true.

    ! message in buffer ?
    if ( len_trim(gol) > 0 ) then

      ! make a copy of the message to avoid problems with re-writing on some machiens:
      gol2 = trim(gol)

      ! error message;
      write (gol,'("ERROR - ",a)') trim(gol2); call goPr

    end if

    ! restore apply flag:
    pr_apply = save_pr_apply

  end subroutine goErr


  ! ***


  subroutine goBug

    ! --- local ----------------------------

    logical   ::  save_pr_apply

    ! --- begin --------------------------------

    ! store original apply flag:
    save_pr_apply = pr_apply
    ! always print debug messages:
    pr_apply = .true.

    ! write message
    write (gol,'("BUG - ",a)') trim(gol); call goPr

    ! restore apply flag:
    pr_apply = save_pr_apply

  end subroutine goBug


  ! ***************************************************************************
  ! ***
  ! *** line indent
  ! ***
  ! ***************************************************************************


  subroutine GO_Print_Indent()

    ! increase indent:
    indent = indent + dindent

  end subroutine GO_Print_Indent


  ! ***


  subroutine GO_Print_DeIndent()

    ! increase indent:
    indent = indent - dindent

  end subroutine GO_Print_DeIndent



end module GO_Print

