import collections
import functools
import glob
import ntpath
import os
import random
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

import fastnumbers
import humanize
import numpy as np
import pandas as pd
import six
from fastnumbers import isint, isfloat
from string_grouper import match_strings

from optimus import ROOT_DIR
from optimus.engines import functions as F  # Used in eval
from optimus.helpers.check import is_url
from optimus.helpers.columns import parse_columns
from optimus.helpers.converter import any_dataframe_to_pandas
from optimus.helpers.core import val_to_list, one_list_to_val
from optimus.helpers.logger import logger
from optimus.helpers.raiseit import RaiseIt
from optimus.infer import is_

F = F  # To do not remove the import accidentally when using pycharm auto clean import feature


def random_int(n=5):
    """
    Create a random string of ints
    :return:
    """
    return str(random.randint(1, 10 ** n))


def collect_as_list(df):
    return df.rdd.flatMap(lambda x: x).collect()


def collect_as_dict(df, limit=None):
    """
    Return a dict from a Collect result
    [(col_name, row_value),(col_name_1, row_value_2),(col_name_3, row_value_3),(col_name_4, row_value_4)]
    :return:
    """

    dict_result = []

    df = any_dataframe_to_pandas(df)

    # if there is only an element in the dict just return the value
    if len(dict_result) == 1:
        dict_result = next(iter(dict_result.values()))
    else:
        col_names = parse_columns(df, "*")

        # Because asDict can return messed columns names we order
        for index, row in df.iterrows():
            # _row = row.asDict()
            r = collections.OrderedDict()
            # for col_name, value in row.iteritems():
            for col_name in col_names:
                r[col_name] = row[col_name]
            dict_result.append(r)
    return dict_result


# def collect_as_dict(df, limit=None):
#     """
#     Return a dict from a Collect result
#     :param df:
#     :return:
#     """
#     # # Explore this approach seems faster
#     # use_unicode = True
#     # from pyspark.serializers import UTF8Deserializer
#     # from pyspark.rdd import RDD
#     # rdd = df._jdf.toJSON()
#     # r = RDD(rdd.toJavaRDD(), df._sc, UTF8Deserializer(use_unicode))
#     # if limit is None:
#     #     r.collect()
#     # else:
#     #     r.take(limit)
#     # return r
#     #
#     from optimus.helpers.columns import parse_columns
#     dict_result = []
#
#     # if there is only an element in the dict just return the value
#     if len(dict_result) == 1:
#         dict_result = next(iter(dict_result.values()))
#     else:
#         col_names = parse_columns(df, "*")
#
#         # Because asDict can return messed columns names we order
#         for row in df.collect():
#             _row = row.asDict()
#             r = collections.OrderedDict()
#             for col in col_names:
#                 r[col] = _row[col]
#             dict_result.append(r)
#     return dict_result


def filter_list(val, index=0):
    """
    Convert a list to None, int, str or a list filtering a specific index
    [] to None
    ['test'] to test

    :param val:
    :param index:
    :return:
    """
    if len(val) == 0:
        return None
    else:
        return one_list_to_val([column[index] for column in val])


def absolute_path(files, format="posix"):
    """
    User project base folder to construct and absolute path
    :param files: path files
    :param format: posix or uri
    :return:
    """
    files = val_to_list(files)
    result = None
    if format == "uri":
        result = [Path(ROOT_DIR + file).as_uri() for file in files]
    elif format == "posix":
        result = [Path(ROOT_DIR + file).as_posix() for file in files]
    else:
        RaiseIt.value_error(format, ["posix", "uri"])

    result = one_list_to_val(result)
    return result


def format_path(path, format="posix"):
    """
    Format a path depending fo the operative system
    :param path:
    :param format:
    :return:
    """
    if format == "uri":
        result = Path(path).as_uri()
    elif format == "posix":
        result = Path(path).as_posix()
    return result


def java_version():
    version = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT)
    pattern = '\"(\d+\.\d+).*\"'
    print(re.search(pattern, version).groups()[0])


def setup_google_colab():
    """
    Check if we are in Google Colab and setup it up
    :return:
    """
    from optimus.helpers.constants import JAVA_PATH_COLAB
    from optimus.engines.spark.constants import SPARK_PATH_COLAB
    from optimus.engines.spark.constants import SPARK_URL
    from optimus.engines.spark.constants import SPARK_FILE

    IN_COLAB = 'google.colab' in sys.modules

    if IN_COLAB:
        if not os.path.isdir(JAVA_PATH_COLAB) or not os.path.isdir(SPARK_PATH_COLAB):
            print("Installing Optimus, Java8 and Spark. It could take 3 min...")
            commands = [
                "apt-get install openjdk-8-jdk-headless -qq > /dev/null",
                "wget -q {SPARK_URL}".format(SPARK_URL=SPARK_URL),
                "tar xf {SPARK_FILE}".format(SPARK_FILE=SPARK_FILE)
            ]

            cmd = " && ".join(commands)

            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            p_stdout = p.stdout.read().decode("ascii")
            p_stderr = p.stderr.read().decode("ascii")
            print(p_stdout, p_stderr)

        else:
            print("Settings env vars")
            # Always configure the env vars

            os.environ["JAVA_HOME"] = JAVA_PATH_COLAB
            os.environ["SPARK_HOME"] = SPARK_PATH_COLAB


def is_pyarrow_installed():
    """
    Check if pyarrow is installed
    :return:
    """
    try:
        import pyarrow
        have_arrow = True
    except ImportError:
        have_arrow = False
    return have_arrow


def check_env_vars(env_vars):
    """
    Check if a environment var exist
    :param env_vars: Environment var name
    :return:
    """

    for env_var in env_vars:
        if env_var in os.environ:
            logger.print(env_var + "=" + os.environ.get(env_var))
        else:
            logger.print(env_var + " is not set")


# Reference https://nvie.com/posts/modifying-deeply-nested-structures/


def ellipsis(data, length=20):
    """
    Add a "..." if a string y greater than a specific length
    :param data:
    :param length: length taking into account to cut the string
    :return:
    """
    data = str(data)
    return (data[:length] + '..') if len(data) > length else data


def create_buckets(lower_bound, upper_bound, bins):
    """
    Create a dictionary with bins
    :param lower_bound: low range
    :param upper_bound: high range
    :param bins: number of buckets
    :return:
    """
    range_value = (upper_bound - lower_bound) / bins
    low = lower_bound

    buckets = []

    if bins == 1:
        buckets.append({"lower": low, "upper": low + 1, "bucket": 0})
    else:
        for i in range(0, bins):
            high = low + range_value
            buckets.append({"lower": low, "upper": high, "bucket": i})
            low = high

        # Ensure that the upper bound is exactly the higher value.
        # Because floating point calculation it can miss the upper bound in the final sum

        buckets[bins - 1]["upper"] = upper_bound
    return buckets


def deep_sort(obj):
    """
    Recursively sort list or dict nested lists
    """

    if isinstance(obj, dict):
        _sorted = {}
        for key in sorted(obj):
            _sorted[key] = deep_sort(obj[key])

    elif isinstance(obj, list):
        new_list = []
        for val in obj:
            new_list.append(deep_sort(val))
        _sorted = sorted(new_list)

    else:
        _sorted = obj

    return _sorted


def infer_dataframes_keys(df_left: pd.DataFrame, df_right: pd.DataFrame):
    """
    Infer the possible key columns in two data frames
    :param df_left:  
    :param df_right: 
    :return: 
    """
    result = []

    df_left = df_left.dropna().astype(str)
    df_right = df_right.dropna().astype(str)

    # Search column names wiht *id* substring
    def check_ids_columns(_df):
        return [x for x in _df.columns if re.search(r"_id| id|id_| id ", x)]

    ids_columns_left = check_ids_columns(df_left)
    ids_columns_right = check_ids_columns(df_right)
    if len(ids_columns_left) == len(ids_columns_right):
        for i, j in zip(ids_columns_left, ids_columns_right):
            result.append((i, j,))

    # Numeric median len
    def min_max_len(_df):

        df_is_int = _df.applymap(lambda value: fastnumbers.isint(value)).sum()
        df_is_int = df_is_int[df_is_int == len(_df)]
        int_columns_names = df_is_int.index.values
        int_columns_df = _df[int_columns_names]
        string_len = int_columns_df.applymap(lambda value: len(value))
        return (int_columns_names, string_len.min().values, string_len.max().values)

    min_max_df_left = min_max_len(df_left)
    min_max_df_right = min_max_len(df_right)

    def median_len(arr, idx):
        """
        Calculate median len of the columns string
        :param arr:
        :param idx:
        :return:
        """
        _min = arr[1][idx]
        _max = arr[2][idx]
        if _min != _max:
            _median = _max - _min
        else:
            _median = _max
        return _median

    for i, col_l in enumerate(min_max_df_left[0]):
        median_left = median_len(min_max_df_left, i)
        for j, col_r in enumerate(min_max_df_right[0]):
            median_right = median_len(min_max_df_right, j)
            if median_left == median_right:
                result.append((col_l, col_r,))

    # String Clustering
    for col_l in df_left:
        for col_r in df_right:
            try:
                m = match_strings(df_left[col_l], df_right[col_r], min_similarity=0.05)
                if len(m) > 0:
                    result.append((col_l, col_r,))
            except ValueError:
                pass
    # Count tuples
    return [(count,) + item for item, count in Counter(result).items()]


def update_dict(d, u):
    """
    Update only the given keys
    :param d:
    :param u:
    :return:
    """
    # python 3.8+ compatibility
    try:
        collectionsAbc = collections.abc
    except ModuleNotFoundError:
        collectionsAbc = collections

    for k, v in six.iteritems(u):
        dv = d.get(k, {})
        if not isinstance(dv, collectionsAbc.Mapping):
            d[k] = v
        elif isinstance(v, collectionsAbc.Mapping):
            d[k] = update_dict(dv, v)
        else:
            d[k] = v
    return d


def reduce_mem_usage(df, categorical=True, categorical_threshold=50, verbose=False):
    """
    Change the columns datatypes to reduce the memory usage. Also identify
    :param df:
    :param categorical:
    :param categorical_threshold:
    :param verbose:
    :return:
    """

    # Reference https://www.kaggle.com/arjanso/reducing-dataframe-memory-size-by-65/notebook

    start_mem_usg = df.ext.size()

    ints = df.applymap(isint).sum().compute().to_dict()
    floats = df.applymap(isfloat).sum().compute().to_dict()
    nulls = df.isnull().sum().compute().to_dict()
    total_rows = len(df)

    columns_dtype = {}
    for x, y in ints.items():

        if ints[x] == nulls[x]:
            dtype = "object"
        elif floats[x] == total_rows:
            dtype = "numerical"
        elif total_rows <= ints[x] + nulls[x]:
            dtype = "numerical"
        else:
            dtype = "object"
        columns_dtype[x] = dtype

    numerical_int = [col for col, dtype in columns_dtype.items() if dtype == "numerical"]
    final = {}

    if len(numerical_int) > 0:
        min_max = df.cols.range(numerical_int)

        import numpy as np
        for col_name in min_max.keys():
            _min = min_max[col_name]["min"]
            _max = min_max[col_name]["max"]
            if _min >= 0:
                if _max < 255:
                    final[col_name] = np.uint8
                elif _max < 65535:
                    final[col_name] = np.uint16
                elif _max < 4294967295:
                    final[col_name] = np.uint32
                else:
                    final[col_name] = np.uint64
            else:
                if _min > np.iinfo(np.int8).min and _max < np.iinfo(np.int8).max:
                    final[col_name] = np.int8
                elif _min > np.iinfo(np.int16).min and _max < np.iinfo(np.int16).max:
                    final[col_name] = np.int16
                elif _min > np.iinfo(np.int32).min and _max < np.iinfo(np.int32).max:
                    final[col_name] = np.int32
                elif _min > np.iinfo(np.int64).min and _max < np.iinfo(np.int64).max:
                    final[col_name] = np.int64
            # print(final[col_name])

    object_int = [col for col, dtype in columns_dtype.items() if dtype == "object"]
    if len(object_int) > 0:
        count_values = df.cols.value_counts(object_int)

    # if categorical is True:
    #     for col_name in object_int:
    #         if len(count_values[col_name]) <= categorical_threshold:
    #             final[col_name] = "category"

    df = df.astype(final)
    mem_usg = df.ext.size()

    if verbose is True:
        print("Memory usage after optimization:", humanize.naturalsize(start_mem_usg))
        print("Memory usage before optimization is: ", humanize.naturalsize(mem_usg))
        print(round(100 * mem_usg / start_mem_usg), "% of the initial size")

    return df


def downloader(url, file_format):
    """
    Send the request to download a file
    """

    def write_file(response, file, chunk_size=8192):
        """
        Load the data from the http request and save it to disk
        :param response: data returned from the server
        :param file:
        :param chunk_size: size chunk size of the data
        :return:
        """
        total_size = response.headers['Content-Length'].strip() if 'Content-Length' in response.headers else 100
        total_size = int(total_size)
        bytes_so_far = 0

        while 1:
            chunk = response.read(chunk_size)
            bytes_so_far += len(chunk)
            if not chunk:
                break
            file.write(chunk)
            total_size = bytes_so_far if bytes_so_far > total_size else total_size

        return bytes_so_far

    # try to infer the file format using the file extension
    if file_format is None:
        filename, file_format = os.path.splitext(url)
        file_format = file_format.replace('.', '')

    i = url.rfind('/')
    data_name = url[(i + 1):]

    headers = {"User-Agent": "Optimus Data Downloader/1.0"}

    req = Request(url, None, headers)

    logger.print("Downloading %s from %s", data_name, url)

    # It seems that avro need a .avro extension file
    with tempfile.NamedTemporaryFile(suffix="." + file_format, delete=False) as f:
        bytes_downloaded = write_file(urlopen(req), f)
        path = f.name

    if bytes_downloaded > 0:
        logger.print("Downloaded %s bytes", bytes_downloaded)

    logger.print("Creating DataFrame for %s. Please wait...", data_name)

    return path


@functools.lru_cache(maxsize=128)
def prepare_path(path, file_format=None):
    """d
    Helper to return the file to be loaded and the file name.
    This will memoise
    :param path: Path to the file to be loaded
    :param file_format: format file
    :return:
    """
    r = []
    if is_url(path):
        file = downloader(path, file_format)
        file_name = ntpath.basename(path)
        r = [(file, file_name,)]
    else:
        for file_name in glob.glob(path, recursive=True):
            r.append((file_name, ntpath.basename(file_name),))
    if len(r) == 0:
        raise Exception("File not found")
    return r


def set_func(pdf, value, where, output_col, parser, default=None):
    """
    Core implementation of the set function
    :param pdf:
    :param value:
    :param where:
    :param output_col:
    :param parser:
    :param default:
    :return:
    """

    col_names = list(filter(lambda x: x != "__match__", pdf.cols.names()))

    profiler_dtype_to_python = {"decimal": "float", "int": "int", "string": "str", "datetime": "datetime",
                                "bool": "bool", "zip_code": "str"}
    df = pdf.cols.cast(col_names, profiler_dtype_to_python[parser])
    try:
        if where is None:
            return eval(value)
        else:
            # Reference https://stackoverflow.com/questions/33769860/pandas-apply-but-only-for-rows-where-a-condition-is-met

            mask = (eval(where))

            if (output_col not in pdf.cols.names()) and (default is not None):
                pdf[output_col] = pdf[default]
            pdf.loc[mask, output_col] = eval(value)
            return pdf[output_col]

    except (ValueError, TypeError) as e:
        logger.print(e)

        # raise
        return np.nan


def set_function_parser(df, value, where, default=None):
    """
    Infer the data type that must be used to make a calculation using the set function
    :param df:
    :param value:
    :param where:
    :return:
    """
    value = str(value)
    where = str(where)

    def prepare_columns(cols):
        """
        Extract the columns names from the value and where clauses
        :param cols:
        :return:
        """
        if cols is not None:
            r = val_to_list([f_col[1:len(f_col) - 1] for f_col in
                             re.findall(r"(df\['[A-Za-z0-9_ -]*'\])", cols.replace("\"", "'"))])
            a = [re.findall(r"'([^']*)'", i)[0] for i in r]

        else:
            a = []
        return a

    if default is None:
        default = []

    # if default is in
    columns = prepare_columns(value) + prepare_columns(where) + val_to_list(default)
    columns = list(set(columns))
    if columns:
        first_columns = columns[0]
        column_dtype = df.cols.infer_profiler_dtypes(first_columns)[first_columns]["dtype"]

    else:
        if fastnumbers.fast_int(value):
            column_dtype = "int"
        elif fastnumbers.fast_float(value):
            column_dtype = "decimal"
        else:
            column_dtype = "string"

    # if column_dtype in PROFILER_NUMERIC_DTYPES:
    #     func = lambda x: fastnumbers.fast_float(x) if x is not None else None
    # elif column_dtype in PROFILER_STRING_DTYPES or column_dtype is None:
    #     func = lambda x: str(x) if not pd.isnull(x) else None

    return columns, column_dtype


# value = "dd/MM/yyyy hh:mm:ss-sss MA"
def match_date(value):
    """
    Returns Create a regex from a string with a date format
    :param value:
    :return:
    """
    formats = ["d", "dd", "M", "MM", "yy", "yyyy", "h", "hh", "H", "HH", "kk", "k", "m", "mm", "s", "ss", "sss", "/",
               ":", "-", " ", "+", "|", "mi"]
    formats.sort(key=len, reverse=True)

    result = []

    start = 0

    end = len(value)
    found = False

    while start < end:
        found = False
        for f in formats:
            if value.startswith(f, start):
                start = start + len(f)
                result.append(f)
                found = True
                break
        if found is False:
            raise ValueError('{} is not a valid date format'.format(value[start]))

    exprs = []
    for f in result:
        # Separators
        if f in ["/", ":", "-", " ", "|", "+", " "]:
            exprs.append("\\" + f)
        # elif f == ":":
        #     exprs.append("\\:")
        # elif f == "-":
        #     exprs.append("\\-")
        # elif f == " ":
        #     exprs.append(" ")
        # elif f == "|":
        #     exprs.append("\\|")
        # elif f == "+":
        #     exprs.append("\\+")

        # Day
        # d  -> 1 ... 31
        # dd -> 01 ... 31

        elif f == "d":
            exprs.append("(3[01]|[12][0-9]|0?[1-9])")
        elif f == "dd":
            exprs.append("(3[01]|[12][0-9]|0[1-9])")

            # Month
        # M  -> 1 ... 12
        # MM -> 01 ... 12
        elif f == "M":
            exprs.append("(1[0-2]|0?[1-9])")
        elif f == "MM":
            exprs.append("(1[0-2]|0[1-9])")

        # Year
        # yy   -> 00 ... 99
        # yyyy -> 0000 ... 9999
        elif f == "yy":
            exprs.append("[0-9]{2}")
        elif f == "yyyy":
            exprs.append("[0-9]{4}")

            # Hours
        # h  -> 1,2 ... 12
        # hh -> 01,02 ... 12
        # H  -> 0,1 ... 23
        # HH -> 00,01 ... 23
        # k  -> 1,2 ... 24
        # kk -> 01,02 ... 24
        elif f == "h":
            exprs.append("(1[0-2]|0?[1-9])")
        elif f == "hh":
            exprs.append("(1[0-2]|0[1-9])")
        elif f == "H":
            exprs.append("(0?[0-9]|1[0-9]|2[0-3]|[0-9])")
        elif f == "HH":
            exprs.append("(0[0-9]|1[0-9]|2[0-3]|[0-9])")
        elif f == "k":
            exprs.append("(0?[1-9]|1[0-9]|2[0-4]|[1-9])")
        elif f == "kk":
            exprs.append("(0[1-9]|1[0-9]|2[0-4])")

        # Minutes
        # m  -> 0 ... 59
        # mm -> 00 .. 59
        elif f == "m":
            exprs.append("[1-5]?[0-9]")
        elif f == "mm":
            exprs.append("[0-5][0-9]")

        # Seconds
        # s  -> 0 ... 59
        # ss -> 00 .. 59
        elif f == "s":
            exprs.append("[1-5]?[0-9]")
        elif f == "ss":
            exprs.append("[0-5][0-9]")

        # Milliseconds
        # sss -> 0 ... 999
        elif f == "sss":
            exprs.append("[0-9]{3}")

        # Extras
        # mi -> Meridian indicator (AM am Am) (PM pm Pm) (m M)
        elif f == "mi":
            exprs.append("([AaPp][Mm]|[Mm]).?")

    return "".join(exprs)


# print("^" + match_date(value) + "$")

def ipython_vars(globals_vars, dtype=None):
    """
    Return the list of data frames depending on the type
    :param globals_vars: globals() from the notebook
    :param dtype: 'pandas', 'cudf', 'dask' or 'dask_cudf'
    :return:
    """
    tmp = globals_vars.copy()
    vars = [(k, v, type(v)) for k, v in tmp.items() if
            not k.startswith('_') and k != 'tmp' and k != 'In' and k != 'Out' and not hasattr(v, '__call__')]

    if dtype == "dask_cudf":
        from dask_cudf.core import DataFrame as DaskCUDFDataFrame
        _dtype = DaskCUDFDataFrame
    elif dtype == "cudf":
        from cudf.core import DataFrame as CUDFDataFrame
        _dtype = CUDFDataFrame
    elif dtype == "dask":
        from dask.dataframe.core import DataFrame
        _dtype = DataFrame
    elif dtype == "pandas":
        import pandas as pd
        PandasDataFrame = pd.DataFrame
        _dtype = PandasDataFrame

    return [name for name, instance, aa in vars if is_(instance, _dtype)]


# Taken from https://github.com/Kemaweyan/singleton_decorator/
class _SingletonWrapper:
    """
    A singleton wrapper class. Its instances would be created
    for each decorated class.
    """

    def __init__(self, cls):
        self.__wrapped__ = cls
        self._instance = None

    def __call__(self, *args, **kwargs):
        """Returns a single instance of decorated class"""
        if self._instance is None:
            self._instance = self.__wrapped__(*args, **kwargs)
        return self._instance


def singleton(cls):
    """
    A singleton decorator. Returns a wrapper objects. A call on that object
    returns a single instance object of decorated class. Use the __wrapped__
    attribute to access decorated class directly in unit tests
    """
    return _SingletonWrapper(cls)
