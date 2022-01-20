"""
This is the main script to be run from the directory root, it will start the Flask application running which one can
then connect to.
"""
# local packages
from plots import *
from utils import *

# initialise
app_simple = Flask(__name__)  # start flask app
app_simple.config['SECRET_KEY'] = os.urandom(32)  # need to generate csrf token as basic security for Flask
CORS(app_simple)  # makes CORS work (aladin notably)


# website pathing
@app_simple.route('/')
@app_simple.route('/index', methods=['GET', 'POST'])
def index_page():
    """
    The main splash page
    """
    source_count = len(all_results)  # count the number of sources
    return render_template('index_simple.html', source_count=source_count)


@app_simple.route('/search', methods=['GET', 'POST'])
def search():
    """
    The searchbar page
    """
    form = SearchForm()  # main searchbar
    if (refquery := form.refsearch.data) is None:  # content in references searchbar
        refquery = ''
    if (query := form.search.data) is None:  # content in main searchbar
        query = ''
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    try:
        results: Optional[pd.DataFrame] = db.search_object(query, fmt='pandas')  # get the results for that object
    except IndexError:
        results = pd.DataFrame()
    refresults: Optional[dict] = db.search_string(refquery, fmt='pandas', verbose=False)  # search all the strings
    try:
        refsources: pd.DataFrame = refresults['Sources']
    except KeyError:
        stringed_results: Optional[str] = None
    else:
        filtered_results: Optional[pd.DataFrame] = results.merge(refsources, on='source', suffixes=(None, 'extra'))
        filtered_results.drop(columns=list(filtered_results.filter(regex='extra')), inplace=True)
        sourcelinks: list = []  # empty list
        if len(filtered_results):
            for src in filtered_results.source.values:  # over every source in table
                urllnk = quote(src)  # convert object name to url safe
                srclnk = f'<a href="/solo_result/{urllnk}" target="_blank">{src}</a>'  # construct hyperlink
                sourcelinks.append(srclnk)  # add that to list
            filtered_results['source'] = sourcelinks  # update dataframe with the linked ones
            query = query.upper()  # convert contents of search bar to all upper case
            stringed_results = markdown(filtered_results.to_html(index=False, escape=False, max_rows=10,
                                                                 classes='table table-dark '
                                                                         'table-bordered table-striped'))
        else:
            stringed_results = None
    return render_template('search.html', form=form, refquery=refquery,
                           results=stringed_results, query=query)  # if everything not okay, return existing page as is


@app_simple.route('/fulltextsearch', methods=['GET', 'POST'])
def fulltextsearch():
    """
    Wrapping the search string function to search through all tables and return them
    """
    form = LooseSearchForm()  # main searchbar
    if (query := form.search.data) is None:  # content in main searchbar
        query = ''
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    results: Dict[str, pd.DataFrame] = db.search_string(query, fmt='pandas', verbose=False)  # search
    resultsout = {}
    if len(results):
        for tabname, df in results.items():
            if 'source' in df:
                sourcelinks = []
                for src in df.source.values:  # over every source in table
                    urllnk = quote(src)  # convert object name to url safe
                    srclnk = f'<a href="/solo_result/{urllnk}" target="_blank">{src}</a>'  # construct hyperlink
                    sourcelinks.append(srclnk)  # add that to list
                df['source'] = sourcelinks  # update dataframe with the linked ones
            if tabname == 'Spectra':
                df = Inventory.spectra_handle(df, False)
            stringed_df: Optional[str] = markdown(df.to_html(index=False, escape=False, max_rows=10,
                                                             classes='table table-dark table-bordered table-striped'))
            resultsout[tabname] = stringed_df
    return render_template('fulltextsearch.html', form=form,
                           results=resultsout, query=query)  # if everything not okay, return existing page


@app_simple.route('/raw_query', methods=['GET', 'POST'])
def raw_query():
    """
    Page for raw sql query, returning all tables
    """
    form = SQLForm()  # main searchbar
    if (query := form.sqlfield.data) is None:  # content in main searchbar
        query = ''
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    try:
        results: Optional[pd.DataFrame] = db.sql_query(query, format='pandas')
    except (ResourceClosedError, OperationalError):
        results = pd.DataFrame()
    sourcelinks = []
    if len(results):
        for src in results.source.values:  # over every source in table
            urllnk = quote(src)  # convert object name to url safe
            srclnk = f'<a href="/solo_result/{urllnk}" target="_blank">{src}</a>'  # construct hyperlink
            sourcelinks.append(srclnk)  # add that to list
        results['source'] = sourcelinks  # update dataframe with the linked ones
        query = query.upper()  # convert contents of search bar to all upper case
        stringed_results = markdown(results.to_html(index=False, escape=False, max_rows=10,
                                                    classes='table table-dark table-bordered table-striped'))
    else:
        stringed_results = None
    return render_template('rawquery.html', form=form, results=stringed_results, query=query)


@app_simple.route('/solo_result/<query>')
def solo_result(query: str):
    """
    The result page for just one object when the query matches but one object

    Parameters
    ----------
    query: str
        The query -- full match to a main ID
    """
    curdoc().template_variables['query'] = query  # add query to bokeh curdoc
    db = SimpleDB(db_file, connection_arguments={'check_same_thread': False})  # open database
    resultdict: dict = db.inventory(query)  # get everything about that object
    everything = Inventory(resultdict, args)  # parsing the inventory into markdown
    scriptcmd, divcmd = camdplot(query, everything, all_bands, all_results_full, all_plx, photfilters,
                                 all_photo, jscallbacks, nightskytheme)
    scriptspectra, divspectra, nfail, failstr = specplot(query, db_file, nightskytheme, jscallbacks)
    query = query.upper()  # convert query to all upper case
    return render_template('solo_result.html', resources=CDN.render(), scriptcmd=scriptcmd, divcmd=divcmd,
                           scriptspectra=scriptspectra, divspectra=divspectra, nfail=nfail, failstr=failstr,
                           query=query, resultdict=resultdict, everything=everything)


@app_simple.route('/multiplot')
def multiplotpage():
    """
    The page for all the plots
    """
    scriptmulti, divmulti = multiplotbokeh(all_results_full, all_bands, all_photo, all_plx, jscallbacks, nightskytheme)
    return render_template('multiplot.html', scriptmulti=scriptmulti, divmulti=divmulti, resources=CDN.render())


@app_simple.route('/autocomplete', methods=['GET'])
def autocomplete():
    """
    Autocompleting function, id linked to the jquery which does the heavy lifting
    """
    return jsonify(alljsonlist=all_results)  # wraps all of the object names as a list, into a .json for server use


@app_simple.route('/feedback')
def feedback_page():
    """
    Page for directing users to github SIMPLE-web page
    """
    return render_template('feedback.html')


@app_simple.route('/schema')
def schema_page():
    """
    Page for directing users to github SIMPLE-db page
    """
    return render_template('schema.html')


if __name__ == '__main__':
    args, db_file, photfilters, all_results, all_results_full, all_photo, all_bands, all_plx = mainutils()
    nightskytheme, jscallbacks = mainplots()
    app_simple.run(host=args.host, port=args.port, debug=args.debug)  # generate the application on server side
