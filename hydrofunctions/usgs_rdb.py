"""
hydrofunctions.usgs_rdb
~~~~~~~~~~~~~~~~~~~~~~~

This module is for working with the various USGS dataservices that use the rdb
text format. These include the statistics service, the field measurements
service, the rating curve service, and the peak discharge service.
"""
import pandas as pd
import requests
from io import StringIO
from IPython.core import display


def read_rdb(text):
    """Read strings that are in rdb format.

    Args:
        test (str):
            A long string containing the contents of a rdb file. A common way
            to obtain these would be from the .text property of a requests
            response, as in the example usage below.
    Returns:
        outputDF (pandas.DataFrame):
            A dataframe containing the information in the rdb file. 'site_no'
            is interpreted as a string, but every other number is interpreted
            as a float or int; missing values as an np.nan; strings for
            everything else.
        columns (list of strings):
            The column names, taken from the rdb header row.
        dtype (list of strings):
            The second header row from the rdb file. These mostly tell the
            column width, and typically record everything as string data ('s')
            type. The exception to this are dates, which are listed with a 'd'.
        header (list of strings):
            Every commented line at the top of the rdb file is marked with a
            '#' symbol. Each of these lines is stored in this output.
    """
    header = []
    datalines = []
    count = 0
    for line in text.splitlines():
        if line[0] == "#":
            header.append(line)
        elif count == 0:
            columns = line.split()
            count = count + 1
        elif count == 1:
            dtype = line.split()
            count = count + 1
        else:
            datalines.append(line)
    data = "\n".join(datalines)

    outputDF = pd.read_csv(
        StringIO(data),
        sep="\t",
        comment="#",
        header=None,
        names=columns,
        dtype={"site_no": str, "parameter_cd": str},
    )

    # outputDF.outputDF.filter(like='_cd').columns
    # TODO: code columns ('*._cd') should be interpreted as strings.

    return outputDF, columns, dtype, header


def field_meas(site):
    """Load USGS field measurements of stream discharge into a Pandas dataframe

    Args:
        site (str):
            The gage ID number for the site.

    Returns:
        a dataframe. Each row represents an observation on a given date of
        river conditions at the gage by USGS personnel. Values are stored in
        columns, and include the measured stream discharge, channel width,
        channel area, depth, and velocity. These data can be used to create a
        rating curve, to estimate the gage height for a discharge of zero, and
        to get readings of water velocity.

    NOTES:
        To plot a rating curve, use:
            `output.plot(x='gage_height_va', y='discharge_va', kind='scatter')`

        Rating curves are typically plotted with the indepedent variable,
        gage_height, plotted on the Y axis.

    Discussion:
        The USGS operates over 8,000 stream gages around the United States and
        territories. Each of these sensors records the depth, or 'stage' of the
        water. In order to translate this stage data into stream discharge, the
        USGS staff creates an empirical relationship called a 'rating curve'
        between the river stage and stream discharge. To construct this curve,
        the USGS personnel visit all of the gage every one to eight weeks, and
        measure the stage and the discharge of the river manually.

        The `field_meas()` function returns all of the field-collected data for
        this site. You can use these data to create your own rating curve or to
        read the notes about local conditions.

        The `rating_curve()` function returns the most recent 'expanded shift-
        adjusted' rating curve constructed for this site.

    """
    url = (
        "https://waterdata.usgs.gov/pa/nwis/measurements?site_no="
        + site
        + "&agency_cd=USGS&format=rdb_expanded"
    )
    headers = {"Accept-encoding": "gzip"}

    print("Retrieving field measurements for site #", site, " from ", url)
    response = requests.get(url, headers=headers)

    # It may be desireable to keep the original na_values, like 'unkn' for many
    # of the columns. However, it is still a good idea to replace for the gage
    # depth and discharge values, since these variables get used in plotting
    # functions.
    outputDF, columns, dtype, header = read_rdb(response.text)
    outputDF.measurement_dt = pd.to_datetime(outputDF.measurement_dt)

    # An attempt to use the tz_cd column to make measurement_dt timezone aware.
    # outputDF.tz_cd.replace({np.nan: 'UTC'}, inplace=True)
    # def f(x, y):
    #    return x.tz_localize(y)
    # outputDF['datetime'] = outputDF[['measurement_dt', 'tz_cd']].apply(lambda x: f(*x), axis=1)

    outputDF.set_index("measurement_dt", inplace=True)

    return outputDF


def peaks(site):
    """Return a series of annual peak discharges.

    Args:
        site(str):
            The gauge ID number for the site.

    Returns:
        a dataframe with the annual peak discharge series.

        a header of meta-data supplied by the USGS with the data series.
    """
    url = (
        "https://nwis.waterdata.usgs.gov/nwis/peak?site_no="
        + site
        + "&agency_cd=USGS&format=rdb"
    )

    headers = {"Accept-encoding": "gzip"}

    print("Retrieving annual peak discharges for site #", site, " from ", url)
    response = requests.get(url, headers=headers)

    outputDF, columns, dtype, header = read_rdb(response.text)
    outputDF.peak_dt = pd.to_datetime(outputDF.peak_dt)

    outputDF.set_index("peak_dt", inplace=True)

    return outputDF


def rating_curve(site):
    """Return the most recent USGS expanded-shift-adjusted rating curve for a
    given stream gage into a dataframe.

    Args:
        site (str):
            The gage ID number for the site.

    Returns:
        a dataframe with the most recent rating curve.

    Note:
        Rating curves change over time
    """
    url = (
        "https://waterdata.usgs.gov/nwisweb/data/ratings/exsa/USGS."
        + site
        + ".exsa.rdb"
    )
    headers = {"Accept-encoding": "gzip"}
    print("Retrieving rating curve for site #", site, " from ", url)
    response = requests.get(url, headers=headers)
    outputDF, columns, dtype, header = read_rdb(response.text)
    outputDF.columns = ["stage", "shift", "discharge", "stor"]
    """
    outputDF = pd.read_csv(StringIO(response.text),
                     sep='\t',
                     comment='#',
                     header=1,
                     names=['stage', 'shift', 'discharge', 'stor'],
                     skiprows=2
                     )
    """
    return outputDF


def stats(site, statReportType="daily", **kwargs):
    """Return statistics from the USGS Stats Service as a dataframe.

    Args:
        site (str):
            The gage ID number for the site, or a series of gage IDs separated
            by commas, like this: '01546500,01548000'.

        statReportType ('annual'|'monthly'|'daily'):
            There are three different types of report that you can request.
            - 'daily' (default): this

    Returns:
        a dataframe with the requested statistics.

    Raises:
        HTTPError when a non-200 http status code is returned.

    Note:
        This function is based on the USGS statistics service, described here:
        https://waterservices.usgs.gov/rest/Statistics-Service.html

        The USGS Statistics Service allows you to specify a wide array of
        additional parameters in your request. You can provide these parameters
        as keyword arguments, like in this example:
        `hf.stats('01452500', parameterCD='00060')`  This will only request
        statistics for discharge, which is specified with the '00060'
        parameter code.

        Additional useful parameters include:

            - `parameterCD='00060,00065'` Limit the request for statistics to
              only one parameter or to a list of parameters. The default behavior
              is to provide statistics for every parameter that has been measured
              at this site. In this example, statistics for discharge ('00060')
              and stage ('00065') are requested.

            - `statYearType='water'` Calculate annual statistics based on the
              water year, which runs from October 1st to September 31st. This
              parameter is only for use with annual reports. If not specified,
              the default behavior will use calendar years for reporting.

            - `missingData='on'`  Calculate statistics even when there are some
              missing values. If not specified, the default behavior is to drop
              years that have fewer than 365 values from annual reports, and to
              drop months that have fewer than 30 values in monthly reports. The
              number of values used to calculate a statistic is reported in the
              'count_nu' column.

            - You can read about other useful parameters here: https://waterservices.usgs.gov/rest/Statistics-Service.html#statistical_Controls

    """
    url = "https://waterservices.usgs.gov/nwis/stat/"

    headers = {
        "Accept-encoding": "gzip",
    }
    # Set default values for parameters that are too obscure to put into call
    # signature.
    params = {
        "statReportType": statReportType,
        "statType": "all",
        "sites": site,
        "format": "rdb",
    }
    # Overwrite defaults if they are specified.
    params.update(kwargs)

    response = requests.get(url, headers=headers, params=params)
    print(
        f"Retrieving {params['statReportType']} statistics for site #{params['sites']} from {response.url}"
    )

    if response.status_code != 200:
        print(f"The USGS has returned an error code of {response.status_code}")
        # If this code is being run inside of a notebook, the USGS error page
        # will be displayed.
        display.display(display.HTML(response.text))
        # raise an exception
        response.raise_for_status()
        # or raise some sort of Hydro http error based on requests http error.
        return response
    else:
        outputDF, columns, dtype, header = read_rdb(response.text)
    return outputDF
