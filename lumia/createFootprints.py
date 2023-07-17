from transport.multitracer import Observations
from pandas import read_csv
import os 

def Change_TimeCol(dataset):
    Obs = read_csv(dataset, parse_dates=["time"], infer_datetime_format="%Y%m%d%H%M%S",index_col=0)
    new_filename = str(os.path.splitext(dataset)[0]) + ".hdf"
    Obs.to_hdf(new_filename, key = "observations")
    #Obs = Observations.read("Obs.hdf")

Change_TimeCol('/home/dkivits/Footprints/Flexpart/DICE/lumia/observations.csv')