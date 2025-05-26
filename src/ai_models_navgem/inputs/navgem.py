import glob
import earthkit.data as ekd
import logging
import numpy as np
import eccodes
import matplotlib.pyplot as plt
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

        #Temporary output grib file
        formatted_pressure_file = f"navgem_data/pres_formatted_{date}_{time}"
        formatted_pressure_output = ekd.new_grib_output(
            formatted_pressure_file, edition=1
        )

        #Loop through template file messages
        for grb in template_pres:

            #Extract message name and level and create template for metadata
            parameter_name = grb['shortName']
            level = grb['level']
            template = grb

            #Set the date and time of template to correct date and time
            eccodes.codes_set(template.handle._handle, "date", int(kwargs['date']))
            eccodes.codes_set(
                template.handle._handle, "time", int(kwargs['time']) * 100
            )

            #Handle specific humidity (missing)
            if parameter_name == "q":
                data_array = np.zeros((721, 1440))

            #For geopotential fields extract geopotential height and convert
            elif parameter_name == "z":
                geopotential_height_data = navgem_data.sel(
                    param="gh", level=level
                )
                data_array = np.flipud(geopotential_height_data[0].to_numpy() * 9.80665)
                #Interpolate from 0.5deg to 0.25deg
                data_array = interpolate(
                                        data_array,
                                        np.arange(90,-90.50,-0.50),
                                        np.arange(0,360,0.50),
                                        np.arange(90,-90.25,-0.25),
                                        np.arange(0,360,0.25)
                                        )

            #Otherwise just select the relevant NAVGEM data
            else:
                parameter_data = navgem_data.sel(
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

            formatted_pressure_output.write(data_array, template=template)

        formatted_pressure_grib = ekd.from_source("file", formatted_pressure_file)
        return formatted_pressure_grib

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

        formatted_surface_file = f"navgem_data/sfc_formatted_{date}_{time}"
        formatted_surface_output = ekd.new_grib_output(
            formatted_surface_file, edition=1
        )

        #Loop through template file messages
        for grb in template_sfc:

            #Extract message name and level and create template for metadata
            parameter_name = grb['shortName']
            level = grb['level']
            template = grb

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
            formatted_surface_output.write(data_array, template=template)

        formatted_surface_grib = ekd.from_source("file", formatted_surface_file)
        return formatted_surface_grib

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
