import glob
import earthkit.data as ekd
import logging
import numpy as np
import eccodes
from earthkit.data import FieldList
from metpy.units import units
from metpy.calc import specific_humidity_from_dewpoint
from .base import RequestBasedInput
from scipy.interpolate import RegularGridInterpolator

class NavgemInput(RequestBasedInput):
    WHERE = "NAVGEM"
    def pl_load_source(self,**kwargs):

        #Extract date and time
        date = str(kwargs['date'])
        time = str(kwargs['time']).zfill(2)

        #Open template pressure level file from ERA5
        template_pres = ekd.from_source("file", "sample_pres.grib")

        #Open NAVGEM data file
        navgem_data = ekd.from_source("file",f"navgem_data/{date}{time}/merged")

        #Extract relevant pressure level variables from NAVGEM data
        pl_vars = ['t','u','v','gh','w','r','depr']
        pl_levs = [1000,925,850,700,600,500,400,300,250,200,150,100,50]
        pl_data = navgem_data.sel(levelType="pl", level=pl_levs, shortName=pl_vars)

        #Create empty field list
        pl_data_with_q = ekd.SimpleFieldList()

        #Add NAVGEM data to empty list
        for grb in pl_data:
            pl_data_with_q.append(grb)

        #Calculate specific humidity and add to list
        for pl_lev in pl_levs:

            #Select temperature data
            t_grb = pl_data.sel(shortName="t", level=pl_lev)
            t_data = t_grb.to_numpy()

            #Select dewpoint depression data
            depr_grb = pl_data.sel(shortName="depr", level=pl_lev)
            depr_data = depr_grb.to_numpy()

            #Calculate dewpoint
            td_data = t_data - depr_data

            #Calculate specific humidity
            q_data = np.array(specific_humidity_from_dewpoint(pl_lev * units.hPa, td_data * units.kelvin).to('kg/kg'))

            #Get a metadata template
            metadata_template = t_grb[0].metadata()

            #Replace metadata name with q (specific humidity)
            metadata_q = metadata_template.override(shortName="q")

            #Create new message
            q_ds = FieldList.from_array(q_data, metadata_q)[0]

            #Have to clone the message to set units
            q_ds_clone = q_ds.clone(units="kg/kg")

            #Append specific humidity data to empty list
            pl_data_with_q.append(q_ds_clone)

        #Another empty field list
        new_pl_data = ekd.SimpleFieldList()
        for grb in pl_data_with_q:
            print(grb)
        #Loop through template file messages
        for grb in template_pres:

            #Extract message name and level and create template for metadata
            parameter_name = grb['shortName']
            level = grb['level']
            template = grb.copy()
            metadata = template.metadata()

            #Set the date and time of template to correct date and time
            eccodes.codes_set(template.handle._handle, "date", int(kwargs['date']))
            eccodes.codes_set(
                template.handle._handle, "time", int(kwargs['time']) * 100
            )

            #For geopotential fields extract geopotential height and convert
            if parameter_name == "z":
                geopotential_height_data = pl_data_with_q.sel(
                    param="gh", level=level
                )
                data_array = np.flipud(geopotential_height_data[0].to_numpy() * 9.80665)

            #Otherwise just select the relevant NAVGEM data
            else:
                parameter_data = pl_data_with_q.sel(
                    param=parameter_name, level=level
                )
                data_array = np.flipud(parameter_data[0].to_numpy())

            #Interpolate from 0.5deg to 0.25deg
            data_array = interpolate(
                                    data_array,
                                    np.arange(90,-90.50,-0.50),
                                    np.arange(0,360,0.50),
                                    np.arange(90,-90.25,-0.25),
                                    np.arange(0,360,0.25)
                                    )

            #Create field list and extract grib message (not sure if needed)
            ds = FieldList.from_array(data_array, metadata)[0]

            #Append to empty field list and return
            new_pl_data.append(ds)

        return new_pl_data

    def sfc_load_source(self,**kwargs):

        #Extract date and time
        date = str(kwargs['date'])
        time = str(kwargs['time']).zfill(2)
        
        #Open template pressure level file from ERA5
        template_sfc = ekd.from_source("file", "sample_sfc.grib")

        #Open NAVGEM data file
        navgem_data = ekd.from_source("file",f"navgem_data/{date}{time}/merged")

        #Extract relevant surface data from NAVGEM data
        sfc_vars = ['2t','msl','10u','10v','100u','100v','pwat','sp','tcwv']
        sfc_data = navgem_data.sel(shortName=sfc_vars)
        #Create empty field list
        new_sfc_data = ekd.SimpleFieldList()

        #Loop through template file messages
        for grb in template_sfc:

            #Extract message name and level and create template for metadata
            parameter_name = grb['shortName']
            level = grb['level']
            template = grb.copy()

            #Set the date and time of template to correct date and time
            eccodes.codes_set(template.handle._handle, "date", int(kwargs['date']))
            eccodes.codes_set(
                template.handle._handle, "time", int(kwargs['time']) * 100
            )

            #For missing fields fill in with zeros
            if parameter_name in ["tp","tcwv","100u","100v"]:
                data_array = np.zeros((721, 1440))
            #For geopotential at surface (orog) and land-sea mask use ERA5 values
            elif parameter_name in ["z", "lsm"]:
                data_array = grb.to_numpy()
            #For everything else select the data from NAVGEM
            else:
                parameter_data = sfc_data.sel(param=parameter_name)
                data_array = np.flipud(parameter_data[0].to_numpy())

                #Interpolate from 0.5deg to 0.25deg
                data_array = interpolate(
                                        data_array,
                                        np.arange(90,-90.50,-0.50),
                                        np.arange(0,360,0.50),
                                        np.arange(90,-90.25,-0.25),
                                        np.arange(0,360,0.25)
                                        )
            #Create field list and extract grib message (not sure if needed)
            ds = FieldList.from_array(data_array, template.metadata())[0]

            #Append message to empty list and return
            new_sfc_data.append(ds)

        return new_sfc_data

    def ml_load_source(self, **kwargs):
        raise NotImplementedError("CDS does not support model levels")

def interpolate(data,inlats,inlons,outlats,outlons):

    #Extend the input data to wrap values
    inlons_extended = np.concatenate(([inlons[-1] - 360], inlons, [inlons[0] + 360]))
    data_extended = np.concatenate((data[:, -1:], data, data[:, :1]), axis=1)

    #Interpolate to new grid
    interpolator = RegularGridInterpolator((inlats, inlons_extended), data_extended, bounds_error=False)
    outlon_grid,outlat_grid = np.meshgrid(outlons,outlats)
    points = np.array([outlat_grid.flatten(),outlon_grid.flatten()]).T
    data_interpolated = interpolator(points).reshape(outlat_grid.shape)

    return data_interpolated
