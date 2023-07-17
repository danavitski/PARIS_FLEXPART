!
! Fortran file units.
!

module GO_FU

  implicit none
  
  
  ! --- in/out ------------------------------
  
  private
  
  public  ::  goStdIn, goStdOut, goStdErr
  public  ::  goFuRange

  
  ! --- const ---------------------------------
  
  ! standard file units
  integer, parameter    ::  goStdErr = 0
  integer, parameter    ::  goStdIn  = 5
  integer, parameter    ::  goStdOut = 6
  
  ! range of file units that may be used by this program:
  integer, parameter    ::  goFuRange(2) = (/0,999/)
  
end module GO_FU


!*********************************************
! Test program to identify unit numbers for standard input etc.
! Compile:
!   f90 -o test.exe test.f90
! Run and see what comes to the terminal:
!   test.exe
! Files named 'fort.<fu>' will be created for not-special units.
! Error message when writing to standard input;
! change the range of file units, uncomment the test lines,
! and execute:
!   echo 'hello' | test.exe
! Change the range of file units if nothing happends.
!
!program test_fu
!
!  integer            ::  fu
!  character(len=10)  ::  s
!  
!  do fu = 0, 10
!    write (*,*) 'try to write to file unit ', fu
!    write (fu,*) 'THIS IS FILE UNIT ', fu
!  end do
!
!  ! uncoment following line to check standard input:
!  !read (5,*) s
!  !print *, 'read from standard input: ', s
!  
!end program test_fu
!
!*********************************************
