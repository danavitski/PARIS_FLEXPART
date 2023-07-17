#!/usr/bin/env bash
#SBATCH -p thin
#SBATCH -t 00:30:00
#SBATCH -n 64
#SBATCH --mail-user=daan.kivits@wur.nl
#SBATCH --mail-type=FAIL,END
#SBATCH --mem=60000M

singularity run --cleanenv --bind /projects:/projects --bind /projects/0/ctdas/awoude/Tvarita/FLEXPART/footprints:/output --bind /gpfs/scratch1/shared/rdkok/4Tvarita/FLEXPART_runs:/scratch --bind /projects/0/ctdas/awoude/Tvarita/FLEXPART:/TvaritaDirectory -H /home/dkivits/FLEXPART:/home runflex.sif --footprints --rc flexpart_co2.yaml --ncpus 32 --start 20180101 --end 20180201
#singularity run --cleanenv --bind /projects:/projects --bind /projects/0/ctdas/awoude/Tvarita/FLEXPART/footprints:/output --bind /gpfs/scratch1/shared/rdkok/4Tvarita/FLEXPART_runs:/scratch --bind /projects/0/ctdas/awoude/Tvarita/FLEXPART:/TvaritaDirectory -H $PWD:/home runflex.sif --footprints --rc flexpart_co2.yaml --ncpus 32 --start 20180101 --end 20180201
#singularity run --cleanenv --bind /projects:/projects --bind /projects/0/ctdas/dkivits/DATA/FLEXPART/code/footprints:/output --bind /gpfs/scratch1/shared/rdkok/4Daan/FLEXPART_runs:/scratch -H $PWD:/home runflex.sif --footprints --rc flexpart_co2.yaml --ncpus 32 --start 20180101 --end 20190101
#singularity run --cleanenv --bind runflex_latest:/runflex --bind /projects:/projects --bind /projects/0/ctdas/dkivits/DATA/FLEXPART/code/footprints:/output --bind /gpfs/scratch1/shared/rdkok/4Daan/FLEXPART_runs:/scratch runflexenv.sif --footprints --rc flexpart_co2.yaml --ncpus 24 --start 20180101 --end 20180301
