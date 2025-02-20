from netCDF4 import Dataset as DS
import numpy as np
import pygrib as pg
import datetime

def grib2nc(model,path,lead,step,date,time,inputmodel):

    # Check if the file is still open
    os.system(f"lsof {args.path}")
    print("BYE")
    if "." in path:
        out = path.rsplit(".",1)[0] + ".nc"
    else:
        out = path + ".nc"

    varmap = {
            "u10": ['10 metre U wind component','m s-1']
            ,"v10": ['10 metre V wind component','m s-1']
            ,"t2": ['2 metre temperature','K']
            ,"msl": ['Pressure reduced to MSL','Pa']
            ,"u100": ['100 metre U wind component','m s-1']
            ,"v100": ['100 metre U wind component','m s-1']
            ,"sp": ['Surface pressure','Pa']
            ,"tcwv": ['Precipitable water','kg m-2']
            ,"apcp": ['6-hr accumulated precipitation','m']
            ,"u": ['U component of wind','m s-1']
            ,"v": ['V component of wind','m s-1']
            ,"t": ['Temperature','K']
            ,"z": ['Geopotential','m2 s-2']
            ,"r": ['Relative humidity', '%']
            ,"q": ['Specific humidity','kg kg-1']
            ,"w": ['Vertical velocity','Pa s-1']
            }

    ec2gfsmap = {
            "u":"u"
            ,"v":"v"
            ,"w":"w"
            ,"z":"z"
            ,"q":"q"
            ,"r":"r"
            ,"t":"t"
            ,"10u":"u10"
            ,"10v":"v10"
            ,"100u":"u100"
            ,"100v":"v100"
            ,"2t":"t2"
            ,"msl":"msl"
            ,"sp":"sp"
            ,"tcwv":"tcwv"
            ,"tp":"apcp"
            }

    unique_pl_vars = []
    unique_sfc_vars = []
    levels = []
    ncdata = {}
    print("BYE2")
    print(path)
    grib = pg.open(path)
    print("BYEtest")
    y_shape,x_shape = grib[1].values.shape
    lats,lons = grib[1].latlons()
    lats = lats[:,0]
    lons = lons[0,:]
    print("BYE3")
    grib.seek(0)
    for grb in grib:
        if grb.levelType=="pl":
            if grb.level not in levels:
                levels.append(grb.level)
            if grb.shortName not in unique_pl_vars:
                unique_pl_vars.append(grb.shortName)
        else:
            if grb.shortName not in unique_sfc_vars:
                unique_sfc_vars.append(grb.shortName)
    print("BYE4")
    levels.sort(reverse=True)
    levelmap = {}

    for c,level in enumerate(levels):
        levelmap[level] = c
    grib.seek(0)
    for pl_var in unique_pl_vars:
        modelvar = ec2gfsmap[pl_var]
        ncdata[modelvar] = {
            'values': np.zeros((lead // step + 1, len(levels), y_shape, x_shape)).astype('float32'),
            'name': varmap[modelvar][0], 'units': varmap[modelvar][1]
        }
    for sfc_var in unique_sfc_vars:
        modelvar = ec2gfsmap[sfc_var]
        ncdata[modelvar] = {
            'values': np.zeros((lead // step + 1, y_shape, x_shape)).astype('float32'),
            'name': varmap[modelvar][0], 'units': varmap[modelvar][1]
        }

    grib.seek(0)
    for grb in grib:
        shortName = grb.shortName
        timestep = int(grb.step/step)
        level = grb.level
        levelType = grb.levelType
        if (shortName=='z' and levelType=='sfc') or shortName not in ec2gfsmap.keys():
            continue
        gfsequivalent = ec2gfsmap[shortName]
        vals = grb.values
        if levelType=='pl':
            levelind = levelmap[level]
            ncdata[gfsequivalent]['values'][timestep, levelind, :, :] = vals
        elif levelType=='sfc':
            ncdata[gfsequivalent]['values'][timestep, :, :] = vals

    f = DS(out, 'w', format='NETCDF4')
    f.createDimension('time', lead//step + 1)
    f.createDimension('level', len(levels))
    f.createDimension('longitude', x_shape)
    f.createDimension('latitude', y_shape)

    initdt = datetime.datetime.strptime(f"{date}{time}","%Y%m%d%H00")
    inityr = str(initdt.year)
    initmnth = str(initdt.month).zfill(2)
    initday = str(initdt.day).zfill(2)
    inithr = str(initdt.hour).zfill(2)
    times = []

    times = []
    for i in np.arange(0,lead + step,step):
        times.append(int((initdt + datetime.timedelta(hours=int(i))).timestamp()))
        # Create time, longitude, latitude, and level variables in the NetCDF file
    create_variable_nochunk(
        f, 'time', ('time',), np.array(times), {
            'long_name': 'Date and Time', 'units': 'seconds since 1970-1-1',
            'calendar': 'standard'
        }
    )
    create_variable_nochunk(
        f, 'longitude', ('longitude',), lons, {
            'long_name': 'Longitude', 'units': 'degree'
        }
    )
    create_variable_nochunk(
        f, 'latitude', ('latitude',), lats, {
            'long_name': 'Latitude', 'units': 'degree'
        }
    )
    create_variable_nochunk(
        f, 'level', ('level',), np.array(
            levels
        ), {'long_name': 'Isobaric surfaces', 'units': 'hPa'}
    )

    # Create variables for each meteorological parameter
    for variable in unique_pl_vars + unique_sfc_vars:
        dims = ('time', 'level', 'latitude', 'longitude') if variable in unique_pl_vars else ('time', 'latitude', 'longitude')
        if 'level' in dims:
            chunksizes = (1,1,y_shape,x_shape)
        else:
            chunksizes = (1,y_shape,x_shape)
        create_variable(
            f, variable, dims, ncdata[ec2gfsmap[variable]]['values'], {
                'long_name': ncdata[ec2gfsmap[variable]]['name'], 'units': ncdata[ec2gfsmap[variable]]['units']
            },
            chunksizes
        )

    f.Conventions = 'CF-1.8'
    f.version = '3_2025-02-20'
    f.model_name = model
    f.initialization_model = inputmodel
    f.initialization_time = '%s-%s-%sT%s:00:00' % (inityr,initmnth,initday,inithr)
    f.first_forecast_hour = "0"
    f.last_forecast_hour = f"{lead}"
    f.forecast_hour_step = f"{step}"
    f.creation_time = (datetime.datetime.utcnow()).strftime('%Y-%m-%dT%H:%M:%S')
    f.close()

def create_variable(f, name, dimensions, data, attrs, chunksizes):
    if name in ['time','level']:
        dtype = 'i4'
    else:
        dtype = 'f4'
    var = f.createVariable(name, dtype, dimensions,compression='zlib',complevel=4,chunksizes=chunksizes)
    var[:] = data
    for attr_name, attr_value in attrs.items():
        var.setncattr(attr_name, attr_value)

def create_variable_nochunk(f, name, dimensions, data, attrs):
    if name in ['time','level']:
        dtype = 'i4'
    else:
        dtype = 'f4'
    var = f.createVariable(name, dtype, dimensions,compression='zlib',complevel=4)
    var[:] = data
    for attr_name, attr_value in attrs.items():
        var.setncattr(attr_name, attr_value)

