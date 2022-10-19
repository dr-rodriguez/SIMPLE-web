"""
The static functions for various calculations and required parameters
"""
import sys

# local packages

sys.path.append('simple_root/simple_app')
from simports import *


def sysargs():
    """
    These are the system arguments given after calling this python script

    Returns
    -------
    _args
        The different argument parameters, can be grabbed via their long names (e.g. _args.host)
    """
    _args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _args.add_argument('-i', '--host', default='127.0.0.1',
                       help='Local IP Address to host server, default 127.0.0.1')
    _args.add_argument('-p', '--port', default=8000,
                       help='Local port number to host server through, default 8000', type=int)
    _args.add_argument('-d', '--debug', help='Run Flask in debug mode?', default=False, action='store_true')
    _args.add_argument('-f', '--file', default='simple_root/SIMPLE.db',
                       help='Database file path relative to current directory, default SIMPLE.db')
    _args = _args.parse_args()
    return _args


class SimpleDB(Database):  # this keeps pycharm happy about unresolved references
    """
    Wrapper class for astrodbkit2.Database specific to SIMPLE
    """
    Sources = None  # initialise class attribute
    Photometry = None
    Parallaxes = None
    Spectra = None
    PhotometryFilters = None
    Versions = None


class Inventory:
    """
    For use in the solo result page where the inventory of an object is queried, grabs also the RA & Dec
    """
    ra: float = 0
    dec: float = 0

    def __init__(self, resultdict: dict, args, **kwargs):
        """
        Constructor method for Inventory

        Parameters
        ----------
        resultdict: dict
            The dictionary of all the key: values in a given object inventory
        """
        self.results: dict = resultdict  # given inventory for a target
        for key in self.results:  # over every key in inventory
            if args.debug:
                print(key)
            if key in REFERENCE_TABLES:  # ignore the reference table ones
                continue
            lowkey: str = key.lower()  # lower case of the key
            mkdown_output: str = self.listconcat(key, **kwargs)  # get in markdown the dataframe value for given key
            setattr(self, lowkey, mkdown_output)  # set the key attribute with the dataframe for given key
        try:
            srcs: pd.DataFrame = self.listconcat('Sources', rtnmk=False)  # open the Sources result
            self.ra, self.dec = srcs.ra[0], srcs.dec[0]
        except (KeyError, AttributeError):
            pass
        return

    @staticmethod
    def spectra_handle(df: pd.DataFrame, dropsource: bool = True):
        """
        Handles spectra, converting files to links

        Parameters
        ----------
        df: pd.DataFrame
            The table for the spectra
        dropsource: bool
            Switch to keep source in the dataframe

        Returns
        -------
        df: pd.DataFrame
            The edited table
        """
        urlinks = []
        for src in df.spectrum.values:  # over every source in table
            srclnk = f'<a href="{src}" target="_blank">Link</a>'  # construct hyperlink
            urlinks.append(srclnk)  # add that to list
        df.drop(columns=[col for col in df.columns if any([substr in col for substr in ('wave', 'flux', 'original')])],
                inplace=True)
        dropcols = ['spectrum', 'local_spectrum', 'regime']
        if dropsource:
            dropcols.append('source')
        df.drop(columns=dropcols, inplace=True, errors='ignore')
        df['<a href="/write_spectra" target="_blank">download</a>'] = urlinks
        df['observation_date'] = df['observation_date'].dt.date
        return df

    def listconcat(self, key: str, rtnmk: bool = True) -> Union[pd.DataFrame, str]:
        """
        Concatenates the list for a given key

        Parameters
        ----------
        key: str
            The key corresponding to the inventory
        rtnmk: bool
            Switch for whether to return either a markdown string or a dataframe

        Returns
        -------
        df: Union[pd.DataFrame, str]
            Either the dataframe for a given key or the markdown parsed string
        """
        obj: List[dict] = self.results[key]  # the value for the given key
        df: pd.DataFrame = pd.concat([pd.DataFrame(objrow, index=[i])  # create dataframe from found dict
                                      for i, objrow in enumerate(obj)], ignore_index=True)  # every dict in the list
        if rtnmk:  # return markdown boolean
            if key == 'Spectra':
                df = self.spectra_handle(df)
            df.rename(columns={s: s.replace('_', ' ') for s in df.columns if 'download' not in s}, inplace=True)
            return markdown(df.to_html(index=False, escape=False,
                                       classes='table table-dark table-bordered table-striped'))  # html then markdown
        return df  # otherwise return dataframe as is


class SearchForm(FlaskForm):
    """
    Searchbar class
    """
    search = StringField('Search for an object:', id='mainsearchfield')  # searchbar
    refsearch = StringField('Filter by full text search:', id='refsearchfield')
    submit = SubmitField('Search', id='querybutton')  # clicker button to send request


class BasicSearchForm(FlaskForm):
    """
    Searchbar class
    """
    search = StringField('Search for an object:', id='mainsearchfield')  # searchbar
    submit = SubmitField('Search', id='querybutton')  # clicker button to send request


class CoordQueryForm(FlaskForm):
    """
    Searchbar class
    """
    query = StringField('Query by coordinate within radius:', id='mainsearchfield')  # searchbar
    submit = SubmitField('Query', id='querybutton')  # clicker button to send request

    def __init__(self, *args, **kwargs):
        super(CoordQueryForm, self).__init__(*args, **kwargs)
        self.db_file: str = kwargs['db_file']
        return

    def validate_query(self, field):
        db = SimpleDB(self.db_file, connection_arguments={'check_same_thread': False})  # open database
        ra, dec, radius = multi_param_str_parse(field.data)
        if not ra:  # i.e. empty string, bad parse
            raise ValidationError('Input must be two or three inputs separated by " "')
        ra, dec, unit = ra_dec_unit_parse(ra, dec)
        try:
            c = SkyCoord(ra=ra, dec=dec, unit=unit)
        except ValueError:
            raise ValidationError('Cannot parse coordinates, check astropy SkyCoord documentation')
        try:
            _ = db.query_region(c, fmt='pandas', radius=radius)
        except Exception as e:
            raise ValidationError(f'Uncaught Error -- {e}')


class LooseSearchForm(FlaskForm):
    """
    Searchbar class
    """
    search = StringField('Search by full text:', id='mainsearchfield')  # searchbar
    submit = SubmitField('Search', id='querybutton')  # clicker button to send request


class BadSQLError(Exception):
    """
    Anything not starting with select in sql query
    """


class SQLForm(FlaskForm):
    """
    Searchbox class
    """
    sqlfield = TextAreaField('Enter SQL query here:', id='rawsqlarea', render_kw={'rows': '4'})
    submit = SubmitField('Query', id='querybutton')

    def __init__(self, *args, **kwargs):
        super(SQLForm, self).__init__(*args, **kwargs)
        self.db_file: str = kwargs['db_file']
        return

    def validate_sqlfield(self, field):
        db = SimpleDB(self.db_file, connection_arguments={'check_same_thread': False})  # open database
        if (query := field.data) is None or query.strip() == '':  # content in main searchbar
            raise ValidationError('Empty field')
        try:
            querylow: str = query.lower()
            if not querylow.startswith('select') or 'from' not in querylow:
                raise BadSQLError('Queries must start with "select" and contain "from".')
            _: Optional[pd.DataFrame] = db.sql_query(query, fmt='pandas')
        except (ResourceClosedError, OperationalError, IndexError, SqliteWarning, BadSQLError) as e:
            raise ValidationError('Invalid SQL: ' + str(e))
        except Exception as e:  # ugly but safe
            raise ValidationError('Uncaught Error: ' + str(e))


class JSCallbacks:
    """
    Converts javascript callbacks into python triple quoted strings
    """
    dropdownx_js = ''
    dropdowny_js = ''
    button_flip = ''
    normslider = ''
    reset_slider = ''

    def __init__(self):
        jsfuncnames = ('dropdownx_js', 'dropdowny_js', 'button_flip', 'normslider', 'reset_slider')
        with open('simple_root/simple_app/simple_callbacks.js', 'r') as fcall:
            whichvar = ''
            outstr = """"""
            for line in fcall:
                for funcname in jsfuncnames:
                    if funcname in line:
                        whichvar = funcname
                        outstr = """"""
                        break
                else:
                    if line.startswith('}'):
                        setattr(self, whichvar, outstr)
                        whichvar = ''
                        outstr = """"""
                        continue
                    outstr = '\n'.join([outstr, line.strip('\n')])


def all_sources(db_file: str):
    """
    Queries the full table to get all the sources

    Parameters
    ----------
    db_file: str
        The connection string to the database

    Returns
    -------
    allresults
        Just the main IDs
    fullresults
        The full dataframe of all the sources
    """
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    fullresults: pd.DataFrame = db.query(db.Sources).pandas()
    allresults: list = fullresults['source'].tolist()  # gets all the main IDs in the database
    return allresults, fullresults


def get_version(db_file: str) -> str:
    """
    Get the version and affiliated data

    Parameters
    ----------
    db_file
        The string pointing to the database file

    Returns
    -------
    vstr
        The stringified version formatted
    """
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    v: pd.DataFrame = db.query(db.Versions).pandas()
    vactive: pd.Series = v.iloc[-2]  # -1 is "latest" or main
    vstr = f'Version {vactive.version}, updated last: {pd.Timestamp(vactive.start_date).strftime("%d %b %Y")} ' \
           f'({vactive.description})'
    return vstr


def find_colours(photodf: pd.DataFrame, allbands: np.ndarray, photfilters: pd.DataFrame):
    """
    Find all the colours using available photometry

    Parameters
    ----------
    photodf: pd.DataFrame
        The dataframe with all photometry in
    allbands: np.ndarray
        All the photometric bands
    photfilters: pd.DataFrame
        The filters

    Returns
    -------
    photodf: pd.DataFrame
        The dataframe with all photometry and colours in
    """
    for band in allbands:  # loop over all bands
        bandtrue = band
        if '(' in band:  # duplicate bands
            bandtrue = band[:band.find('(')]
        if bandtrue not in photfilters.columns:  # check if we have this in the dictionary
            raise KeyError(f'{bandtrue} not yet a supported filter')
        for nextband in allbands:  # over all bands
            if band == nextband:  # don't make a colour of same band (0)
                continue
            nextbandtrue = nextband
            if '(' in nextband:  # duplicate bands
                nextbandtrue = nextband[:nextband.find('(')]
            if nextbandtrue not in photfilters.columns:  # check if we have this in dictionary
                raise KeyError(f'{nextbandtrue} not yet a supported filter')
            if photfilters.at['effective_wavelength', bandtrue] >= \
                    photfilters.at['effective_wavelength', nextbandtrue]:  # if not blue-red
                continue
            try:
                photodf[f'{band}-{nextband}'] = photodf[band] - photodf[nextband]  # colour
            except KeyError:
                photodf[f'{band}-{nextband}'] = photodf[bandtrue] - photodf[nextband]  # colour for full sample
    return photodf


def parse_photometry(photodf: pd.DataFrame, allbands: np.ndarray, multisource: bool = False) -> pd.DataFrame:
    """
    Parses the photometry dataframe handling multiple references for same magnitude

    Parameters
    ----------
    photodf: pd.DataFrame
        The dataframe with all photometry in
    allbands: np.ndarray
        All the photometric bands
    multisource: bool
        Switch whether to iterate over initial dataframe with multiple sources

    Returns
    -------
    newphoto: pd.DataFrame
        DataFrame of effectively transposed photometry
    """

    def replacer(val: int) -> str:
        """
        Swapping an integer value for a string denoting the value

        Parameters
        ----------
        val: int
            The input number

        Returns
        -------
        _: str
            The formatted string of the value
        """
        if not val:
            return ''
        return f'({val})'

    def one_source_iter(onephotodf: pd.DataFrame):
        """
        Parses the photometry dataframe handling multiple references for same magnitude for one object

        Parameters
        ----------
        onephotodf: pd.DataFrame
            The dataframe with all the photometry in it

        Returns
        -------
        thisnewphot: pd.DataFrame
            DataFrame of transposed photometry
        """
        onephotodf.set_index('band', inplace=True)  # set the band as the index
        thisnewphot: pd.DataFrame = onephotodf.loc[:, ['magnitude']].T  # flip the dataframe and keep only mags
        s = pd.Series(thisnewphot.columns)  # the columns as series
        scc = s.groupby(s).cumcount()  # number of duplicate bands
        thisnewphot.columns += scc.map(replacer)  # fill the duplicate values as (N)
        return thisnewphot

    if not multisource:
        newphoto = one_source_iter(photodf)
    else:
        photodfgrp = photodf.groupby('source')
        newdict = {col: np.empty(len(photodfgrp)) for col in allbands}  # empty dict
        newdict['target'] = np.empty(len(photodfgrp), dtype=str)
        newphoto = pd.DataFrame(newdict)
        for i, (target, targetdf) in tqdm(enumerate(photodfgrp), total=len(photodfgrp), desc='Photometry'):
            specificphoto = one_source_iter(targetdf)  # get the dictionary for this object photometry
            for key in newphoto.columns:  # over all keys
                if key == 'target':
                    newphoto.at[i, key] = target
                else:
                    try:
                        newphoto.at[i, key] = specificphoto.at['magnitude', key]  # append the list for given key
                    except KeyError:  # if that key wasn't present for the object
                        newphoto.at[i, key] = None  # use None as filler
    return newphoto


def all_photometry(db_file: str, photfilters: pd.DataFrame):
    """
    Get all the photometric data from the database to be used in later CMD as background

    Parameters
    ----------
    db_file: str
        The connection string to the database
    photfilters: pd.DataFrame
        The dataframe of the filters

    Returns
    -------
    allphoto: pd.DataFrame
        All the photometry in a dataframe
    allbands: np.ndarray
        The unique passbands to create dropdowns by
    """
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    allphoto: pd.DataFrame = db.query(db.Photometry).pandas()  # get all photometry
    allbands: np.ndarray = allphoto.band.unique()  # the unique bands
    allphoto: pd.DataFrame = parse_photometry(allphoto, allbands, True)  # transpose photometric table
    allphoto = find_colours(allphoto, allbands, photfilters)  # get the colours
    return allphoto, allbands


def all_parallaxes(db_file: str):
    """
    Get the parallaxes from the database for every object

    Returns
    -------
    allplx: pd.DataFrame
        The dataframe of all the parallaxes
    """
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    allplx: pd.DataFrame = db.query(db.Parallaxes).pandas()  # get all photometry
    allplx = allplx[['source', 'parallax', 'adopted']]
    return allplx


def absmags(df: pd.DataFrame, all_bands: np.ndarray) -> pd.DataFrame:
    """
    Calculate all the absolute magnitudes in a given dataframe

    Parameters
    ----------
    df: pd.DataFrame
        The input dataframe
    all_bands: np.ndarray
        The photometric bands

    Returns
    -------
    df: pd.DataFrame
        The output dataframe with absolute mags calculated
    """

    def pogsonlaw(m: Union[float, np.ndarray], dist: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Distance modulus equation

        Parameters
        ----------
        m
            The apparent magnitude
        dist
            The distance in pc
        Returns
        -------
        _
            Absolute magnitude
        """
        return np.where(dist > 0, m - 5 * np.log10(dist, where=dist > 0) + 5, np.nan)

    df['dist'] = np.divide(1000, df.parallax, where=df.parallax > 0)
    for mag in all_bands:
        abs_mag = "M_" + mag
        try:
            df[abs_mag] = pogsonlaw(df[mag], df['dist'])
        except KeyError:
            df[abs_mag] = pogsonlaw(df[mag[:mag.find('(')]], df['dist'])
    return df


def results_concat(all_results_full: pd.DataFrame, all_photo: pd.DataFrame,
                   all_plx: pd.DataFrame, all_bands: np.ndarray) -> pd.DataFrame:
    """
    Gets parallax, photometry and projected positions into one dataframe
    Parameters
    ----------
    all_results_full
        Basic data for all the objects
    all_photo
        All the photometry
    all_plx
        All the parallaxes
    all_bands
        All the photometric bands

    Returns
    -------
    all_results_mostfull: pd.DataFrame
        Concatenated data for all the objects
    """
    raproj, decproj = coordinate_project(all_results_full)  # project coordinates to galactic
    all_results_full['raproj'] = raproj  # ra
    all_results_full['decproj'] = decproj  # dec
    all_results_full_cut: pd.DataFrame = all_results_full[['source', 'raproj', 'decproj']]  # cut dataframe
    all_results_mostfull: pd.DataFrame = pd.merge(all_results_full_cut, all_photo,
                                                  left_on='source', right_on='target', how='left')
    all_results_mostfull = pd.merge(all_results_mostfull, all_plx, on='source')
    all_results_mostfull = absmags(all_results_mostfull, all_bands)  # find the absolute mags
    all_results_mostfull.drop_duplicates('source', inplace=True)
    return all_results_mostfull


def coordinate_project(all_results_full: pd.DataFrame):
    """
    Projects RA and Dec coordinates onto Mollweide grid

    Returns
    -------
    raproj: np.ndarray
        The projected RA coordinates
    decproj: np.ndarray
        The projected DEC coordinates
    """

    def fnewton_solve(thetan: float, phi: float, acc: float = 1e-4) -> float:
        """
        Solves the numerical transformation to project coordinate

        Parameters
        ----------
        thetan: float
            theta in radians
        phi: float
            phi in raidans
        acc: float
            Accuracy of calculation

        Returns
        -------
        thetan: float
            theta in radians
        """
        thetanp1 = thetan - (2 * thetan + np.sin(2 * thetan) - np.pi * np.sin(phi)) / (2 + 2 * np.cos(2 * thetan))
        if np.isnan(thetanp1):  # at pi/2
            return phi
        elif np.abs(thetanp1 - thetan) / np.abs(thetan) < acc:  # less than desired accuracy
            return thetanp1
        else:
            return fnewton_solve(thetanp1, phi)

    @np.vectorize
    def project_mollweide(ra: Union[np.ndarray, float], dec: Union[np.ndarray, float]):
        """
        Mollweide projection of the co-ordinates, see https://en.wikipedia.org/wiki/Mollweide_projection

        Parameters
        ----------
        ra
            Longitudes (RA in degrees)
        dec
            Latitudes (Dec in degrees)

        Returns
        -------
        x
            Projected RA
        y
            Projected DEC
        """
        r = np.pi / 2 / np.sqrt(2)
        theta = fnewton_solve(dec, dec)  # project
        x = r * (2 * np.sqrt(2)) / np.pi * ra * np.cos(theta)
        y = r * np.sqrt(2) * np.sin(theta)
        x, y = np.rad2deg([x, y])  # back to degrees
        return x, y

    ravalues: np.ndarray = all_results_full.ra.values  # all ra values
    decvalues: np.ndarray = all_results_full.dec.values  # all dec values
    allcoords = SkyCoord(ravalues, decvalues, unit='deg', frame='icrs')  # make astropy skycoord object
    ravalues = allcoords.galactic.l.value  # convert to galactic
    decvalues = allcoords.galactic.b.value  # convert to galactic
    ravalues -= 180  # shift position
    ravalues = np.array([np.abs(180 - raval) if raval >= 0 else -np.abs(raval + 180) for raval in ravalues])
    ravalues, decvalues = np.deg2rad([ravalues, decvalues])  # convert to radians
    raproj, decproj = project_mollweide(ravalues, decvalues)  # project to Mollweide
    return raproj, decproj


def onedfquery(results: pd.DataFrame, tid: Optional[str] = None, limmaxrows: bool = False) -> Optional[str]:
    """
    Handling the output from a query that returns only one dataframe

    Parameters
    ----------
    results
        The dataframe of results for the query
    tid
        The table id to be passed to html
    limmaxrows
        Limit max rows switch

    Returns
    -------
    stringed_results
        Results converted into markdown including links where there is a source
    """
    if tid is None:
        tid = 'searchtable'
    if len(results):
        if 'source' in results.columns:
            sourcelinks = []
            for src in results.source.values:  # over every source in table
                urllnk = quote(src)  # convert object name to url safe
                srclnk = f'<a href="/load_solo/{urllnk}" target="_blank">{src}</a>'  # construct hyperlink
                sourcelinks.append(srclnk)  # add that to list
            results['source'] = sourcelinks  # update dataframe with the linked ones
        if limmaxrows:
            stringed_results = markdown(results.to_html(index=False, escape=False, table_id=tid, max_rows=50,
                                                        classes='table table-dark table-bordered table-striped'))
        else:
            stringed_results = markdown(results.to_html(index=False, escape=False, table_id=tid,
                                                        classes='table table-dark table-bordered table-striped'))
    else:
        stringed_results = None
    return stringed_results


def multidfquery(results: Dict[str, pd.DataFrame], limmaxrows: bool = False) -> Dict[str, Optional[str]]:
    """
    Handling the output from a query which returns multiple dataframes

    Parameters
    ----------
    results
        The dictionary of dataframes
    limmaxrows
        Limit max rows switch

    Returns
    -------
    resultsout
        The dictionary of handled dataframes
    """
    resultsout = {}
    if len(results):
        for tabname, df in results.items():  # looping through dictionary
            stringed_df = onedfquery(df, tabname.lower() + 'table', limmaxrows)  # handle each dataframe
            resultsout[tabname] = stringed_df
    return resultsout


def multi_param_str_parse(s: str) -> Optional[Tuple[str, str, float]]:
    """
    Parses a string to split into two or three parameters separated by N spaces

    Parameters
    ----------
    s: str
        Input string

    Returns
    -------
    a
        First output
    b
        Second output
    c
        Third output (optional)
    """
    try:
        qrysplit: np.ndarray = np.array(s.replace('\t', ' ').lower().strip().split(' '))
        qrysplit = qrysplit[np.logical_not(qrysplit == '')]
        qrylen = len(qrysplit)
        if qrylen < 2 or qrylen > 3:
            raise ValueError
        elif qrylen == 3:
            _ = float(qrysplit[2])  # if radius can't be parsed as float, raises ValueError
    except ValueError:
        return '', '', 10.
    if qrylen == 3:
        a, b, c = qrysplit
        c = float(c)
    else:  # only ra and dec
        a, b = qrysplit
        c = 10.
    return a, b, c


def ra_dec_unit_parse(ra: str, dec: str) -> Tuple[Union[str, float], Union[str, float], str]:
    """
    Parses ra and dec values into either string (hms) or float (deg)

    Parameters
    ----------
    ra: str
        RA from string
    dec: str
        Dec from string

    Returns
    -------
    ra
        RA either string or float
    dec
        Dec either string or float
    unit
        Unit as a string
    """
    try:
        ra = float(ra)
        dec = float(dec)
    except ValueError:
        unit = 'hourangle,deg'
    else:
        unit = 'deg'
    return ra, dec, unit


def get_filters(db_file: str) -> pd.DataFrame:
    """
    Query the photometry filters table

    Parameters
    ----------
    db_file: str
        The connection string to the database

    Returns
    -------
    phot_filters: pd.DataFrame
        All of the filters, access as: phot_filters.at['effective_wavelength', <bandname>]
    """
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})
    phot_filters: pd.DataFrame = db.query(db.PhotometryFilters).pandas().set_index('band').T
    return phot_filters


def write_file(results: pd.DataFrame) -> str:
    """
    Creates a csv file ready for download

    Parameters
    ----------
    results: pd.DataFrame
        The dataframe to be written

    Returns
    -------
    fname: str
        The filename
    """
    [os.remove('simple_app/tmp/' + f) for f in os.listdir('simple_app/tmp/') if 'README' not in f]  # clear out
    nowtime = strftime("%Y-%m-%d--%H-%M-%S", localtime())
    fname = 'simple_app/tmp/userquery-' + nowtime + '.csv'
    results.to_csv(fname, index=False)
    return fname


def write_multifiles(resultsdict: Dict[str, pd.DataFrame]) -> str:
    """
    Creates a csv file ready for download

    Parameters
    ----------
    resultsdict: Dict[str, pd.DataFrame]
        The collection of dataframes

    Returns
    -------
    fname: str
        The filename
    """
    [os.remove('simple_app/tmp/' + f) for f in os.listdir('simple_app/tmp/') if 'README' not in f]  # clear out
    nowtime = strftime("%Y-%m-%d--%H-%M-%S", localtime())
    fname = 'simple_app/tmp/userquery-' + nowtime + '.zip'
    for key, df in resultsdict.items():
        csvname = fname.replace('.zip', f'_{key}.csv')
        df.to_csv(csvname, index=False)
    with ZipFile(fname, 'w') as zipper:
        for dirname, subdirname, filenames in os.walk('simple_app/tmp'):
            for csvname in filenames:
                if nowtime not in csvname or 'csv' not in csvname:
                    continue
                fpath = os.path.join(dirname, csvname)
                zipper.write(fpath, os.path.basename(csvname))
    return fname


def write_fitsfiles(fitsfiles: List[str]) -> str:
    """
    Creates a csv file ready for download

    Parameters
    ----------
    fitsfiles: List[str]
        The urls to the fits files

    Returns
    -------
    fname: str
        The filename
    """
    [os.remove('simple_app/tmp/' + f) for f in os.listdir('simple_app/tmp/') if 'README' not in f]  # clear out
    nowtime = strftime("%Y-%m-%d--%H-%M-%S", localtime())
    fname = 'simple_app/tmp/userquery-' + nowtime + '.zip'
    for i, fitsfile in enumerate(fitsfiles):
        fitsname = fname.replace('.zip', f'_{i}.{fitsfile.split(".")[-1]}')
        with open(fitsname, 'wb') as handle:
            r = requests.get(fitsfile)
            for data in r.iter_content():
                handle.write(data)
    with ZipFile(fname, 'w') as zipper:
        for dirname, subdirname, filenames in os.walk('simple_app/tmp'):
            for fitsname in filenames:
                if nowtime not in fitsname or 'zip' in fitsname:
                    continue
                fpath = os.path.join(dirname, fitsname)
                zipper.write(fpath, os.path.basename(fitsname))
    return fname


def mainutils():
    """
    Control module called when grabbing all instances from utils scripts.
    """
    _args = sysargs()  # get all system arguments
    _db_file = f'sqlite:///{_args.file}'  # the database file
    _phot_filters = get_filters(_db_file)  # the photometric filters
    _all_results, _all_results_full = all_sources(_db_file)  # find all the objects once
    _versionstr = get_version(_db_file)  # get version
    _all_photo, _all_bands = all_photometry(_db_file, _phot_filters)  # get all the photometry
    _all_plx = all_parallaxes(_db_file)  # get all the parallaxes
    return _args, _db_file, _phot_filters, _all_results, _all_results_full, _versionstr, \
        _all_photo, _all_bands, _all_plx


if __name__ == '__main__':
    ARGS, DB_FILE, PHOTOMETRIC_FILTERS, ALL_RESULTS, ALL_RESULTS_FULL, VERSION_STR, \
        ALL_PHOTO, ALL_BANDS, ALL_PLX = mainutils()
