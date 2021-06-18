"""Tools for parsing out data from logs.

This module contains the main set of tools to load data from logs.
You can write your own loaders by sub-classing OxLogReader. See
docs on that for more details.
"""

import pickle
import logging
import re
import datetime
import typing
import gzip
import json

try:
    import boto3
except Exception as problem:  # pylint: disable=broad-except
    logging.error('Unable to import from boto3 because "%s"\n%s',
                  str(problem), 'AWS connections will not work.')

try:
    import eyap
except Exception as bad:  # pylint: disable=broad-except
    logging.error('Unable to import eyap for ox_log: %s', str(bad))
    logging.error('You must install eyap to use EyapReader.')
    raise


from ox_log.core import utils


class LogItem:
    """Basic log item.

The LogItem class is what OxLogReader and its subclasses are expected
to return.

All log items should provide at a minimum the following fields:

    timestamp:  Ideally a string timestamp. Regardless of the format,
                the timestamp_to_date must return a datetime.date.
    summary:    A one line summary of the log item.
    body:       A string (possibly in JSON format) for the main body
                of the log item.
"""

    def __init__(self, timestamp, summary, body, data=None):
        self.timestamp = timestamp
        self.summary = summary
        self.body = body
        self.data = dict(data)

    def pretty(self) -> str:
        "Return pretty string representation."
        data = '\n  '.join(['%s=%s' % (n, repr(getattr(self, n)))
                            for n in ['timestamp', 'summary', 'body',
                                      'data']])
        return '%s(%s)' % (self.__class__.__name__, data)

    def __repr__(self):
        return self.pretty()

    def timestamp_to_date(self):
        """Convert self.timestamp to a datetime.date and return that.
        """
        if isinstance(self.timestamp, str):
            return utils.parse_date(self.timestamp)
        to_date = getattr(self.timestamp, 'date', None)
        if to_date is not None:
            return to_date()
        if isinstance(self.timestamp, datetime.date):
            return self.timestamp

        raise ValueError('Could not convert LogItem.timestamp to date')


class OxLogReader:
    """Base class for a log reader.
    """

    def read(self, topic: str, config_kwargs: dict = None):
        """Read data for the given topic.

        :param topic:   String indicating topic to read from. This is
                        specific to the given log reader. It could be
                        the subject line of a discussion thread, the name
                        of a log file, a regular expression, or something
                        else.

        :param config_kwargs:  Sub-class specific dictionary

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  A sequence of LogItem instances (or things that look
                  like LogItem instances). Usually this is a list but
                  could be some other iterable.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Read data from the log. Sub-classes must override
                  this to implement their own log readers.

        """
        raise NotImplementedError

    def name(self):
        """Return string name of reader.

This is used when displaying information about the reader.
"""
        return self.__class__.__name__

    def describe(self):
        """Provide string description of the reader.

This is used when displaying information about the reader.
"""
        doc = self.__doc__
        if not doc or doc == OxLogReader.__doc__:
            doc = 'undocumented'
        return doc


class FileReader(OxLogReader):
    """Subclass of OxLogReader to read data from a file.

This is used for reading log files where each line is a log item.
    """

    def __init__(self, my_re=(
            r'^(?P<timestamp>[^|]+)\|(?P<summary>[^|]+)\|(?P<body>[^|]+)$'),
                 rstrip_body=True):
        r"""Initializer.

        :param my_re:  Optional regular expression to get the timestamp,
                       summary, and body for a line in the log file. If
                       not provided we use:

           r'^(?P<timestamp>[^|]+)\|(?P<summary>[^|]+)\|(?P<body>[^|]+)$'

                       The regular expression should use python's ?P<...>
                       form so that we can ask for the pieces of a LogItem.

        :param rstrip_body=True:    Whether to strip whitespace from the
                                    right of a line in the logfile. Having
                                    this as True is helpful since each line
                                    usually ends in a newline anyway.

        """
        super().__init__()
        self.rstrip_body = rstrip_body
        self.my_re = re.compile(my_re) if isinstance(my_re, str) else my_re

    def read(self, topic, config_kwargs=None):
        """Read data for a given topic as required by OxLogReader.read.

We interpret topic as the name of a file and simply go through that file
line by line parsing out the LogItem instances we can.
        """
        result = []
        with open(topic) as my_fd:
            for num, line in enumerate(my_fd):
                match = self.my_re.match(line)
                if not match:
                    logging.warning('Unable to parse line %s(%i): %s; skip',
                                    topic, num, line)
                    continue
                body = match.group('body')
                if self.rstrip_body:  # Removes whitespace from the right
                    body = body.rstrip()
                result.append(LogItem(match.group('timestamp'),
                                      match.group('summary'), body))

        return result


class AWSBucketReader(OxLogReader):
    """Sub-class of OxLogReader to read from AWS Bucket.
    """

    def read(self, topic, config_kwargs=None):
        """Read data from AWS bucket as required by OxLogReader.read method.

This method interprets the topic as the bucket name and prefix. For example,
if you have a bucket named `my.bucket` with prefix `210618`, you would
provide topic of `my.bucket/210618`.
        """
        result = []
        key_regexp = config_kwargs.pop('key_regexp', '.')
        my_re = re.compile(key_regexp)
        session = boto3.Session(**dict(config_kwargs))
        conn = session.client('s3')
        bucket, *prefix = topic.split('/')
        prefix = '/'.join(prefix)
        if not prefix.strip():
            prefix = None
        objects = conn.list_objects(Bucket=bucket, Prefix=prefix)
        for item in objects['Contents']:
            if my_re.match(item['Key']):
                result.extend(self.logitems_from_s3(conn, bucket, item['Key']))
            else:
                logging.debug('Skip key %s', item['Key'])
        return result

    @staticmethod
    def logitems_from_s3(conn, bucket:str, key: str) -> typing.List[LogItem]:
        """Helper to get data from S3 and convert to LogItem list.

        :param conn:    An s3.client connection to AWS.

        :param bucket:   String name of bucket.

        :param key:   AWS Key for file to read.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  List of LogItem instances parsed from the file.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Read data from an AWS bucket containing JSON log data.

        """
        obj = conn.get_object(Bucket=bucket, Key=key)
        body = obj['Body'].read()
        data = gzip.decompress(body)
        data = data.decode('utf8')
        results = []
        for item in data.split('\n'):
            if not item:
                continue
            jitem = json.loads(item)
            if 'AWSKey' not in item:
                jitem['AWSKey'] = key
            results.append(LogItem(
                jitem['@timestamp'], jitem['message'], jitem['message'],
                data=jitem))
        return results


class PickleReader(OxLogReader):
    """Sub-class of OxLogReader for pickled data.
    """

    def read(self, topic, config_kwargs=None):
        """Read data from pickled file as requierd by OxLogReader.read.

This method interprets topic as the name of a binary file representing
a sequence of pickled LogItem instances. We simply deserialize the
pickle file and return the result.
        """
        return pickle.load(open(topic, 'rb'))


class EyapReader(OxLogReader):
    """Sub-class of OxLogReader using the eyap package.

See documentation for the eyap package at https://github.com/emin63/eyap.
Roughly speaking, eyap provides a common framework to read or write data
to things like a file, a redis database, github, and so on. Using an eyap
reader lets you easily pull data from a variety of sources.

This reader will only import eyap at the last possible moment when
the read method is called. That way you don't have to install eyap
if you don't want to use it.
    """

    def __init__(self, **eyap_kwargs):
        """Initializer.

        :param **eyap_kwargs: Keyword arguments that can be passed
                              to eyap.Make.comment_thread(topic,**eyap_kwargs)
                              to make an eyap comment thread.

        """
        self.eyap_kwargs = dict(eyap_kwargs)

    def read(self, topic, config_kwargs=None):
        """Create eyap reader via something like

        my_thread = eyap.Make.comment_thread(topic=topic, **self.eyap_kwargs)

           and call my_thread.lookup_comments() to get the log data.
        """
        my_thread = eyap.Make.comment_thread(topic=topic, **self.eyap_kwargs)
        return my_thread.lookup_comments()


class LoaderConfig:
    """Configuration for LogLoader.

You must pass a LoaderConfig instance to LogLoader. The config may be
basically empty and you can update it later if desired.

This basically contains two properties:

    readers:  A dictionary with string keys naming readers and values
              being instances of OxLogReader. For example, you might
              provide something like

          {'log_file_reader': FileReader(), 'pickle_reader': PickleReader()}

              to associate a few names to various OxLogReader instances.

    topics:   A dictionary where keys are topic names and values are
              dictionaries of configuration information for that topic.
              The following illustrates an example:

          {'/tmp/oldlog.pkl': 'pickle_reader', 'syslog.txt': 'log_file_reader'}

              In the example above, we are associating the
              topic '/tmp/oldlog.pkl' with the 'pickle_reader' name which
              was defined in the readers example and the 'syslog.txt' topic
              with the 'log_file_reader'. This is basically telling the
              system that when the user wants to see information for say
              'syslog.txt' it can lookup 'log_file_reader' which refers
              to a FileReader() and pull the data.

    """

    def __init__(self, readers=None, topics=None):
        """Initializer.

        :param readers=None:  Optional dictionary for readers. See class
                              docs for details.

        :param topics=None:   Optional dictionary for topics. See class
                              docs for details.

        """
        self.topics = topics if topics else {}
        self.readers = readers if readers else {}

    def lookup_reader(self, reader):
        """Lookup the named reader in self.readers.

        :param reader:   String name of a reader in self.readers.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  The OxLogReader instance named by the `reader` param.

        """
        if isinstance(reader, str):
            reader_name = reader
            reader = self.readers.get(reader_name, None)
            if reader is None:
                raise KeyError(
                    'Could not find reader "%s" in known readers: %s' % (
                        reader_name, '\n'.join(sorted(self.readers))))
        assert isinstance(reader, OxLogReader), (
            'Exepcted reader "%s" to be instance of OxLogReader' % str(
                reader))
        return reader

    def load_reader(self, topic):
        """Find the reader for the given topic.

        :param topic:   String name of a topic in self.topics.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  The reader specified for this topic.

        """
        tconfig = self.topics[topic]
        reader = tconfig['reader']
        reader = self.lookup_reader(reader)
        return reader


class LogLoader:
    """Main class to load and read logs.
    """

    def __init__(self, config=None):
        """Initializer.

        :param config=None:    Optional instance of LoaderConfig. You can
                               provide a new one later with set_config.
        """
        self.config = None
        self.cache = {'topics': {}, 'last_updated_utc': None,
                      'problems': []}

        self.set_config(config if config else LoaderConfig())

    def set_config(self, config):
        """Set the configuration for the loader.

        :param config:     Instance of LoaderConfig.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Set the config to the given value and call self.reset_cache.

        """
        self.config = config
        self.reset_cache()

    def reset_cache(self):
        """Reset the cache.

Users usually do not need to call this. It is meant to be called mainly
by set_config.
        """
        self.cache = {'last_updated_utc': None, 'topics': {},
                      'problems': []}
        for topic, kwargs in self.config.topics.items():
            reader = kwargs['reader']
            self.add_topic(topic, reader)

    def drop_topic(self, topic):
        """Drop the named topic from the config and cache.

        :param topic:    String name of topic to drop.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Each time you call self.refresh, all known topics are
                  updated if possible. You can drop a topic if you are
                  no longer interested and don't want to spend time
                  loading it in refresh.
        """
        self.config.topics.pop(topic, None)
        self.cache['topics'].pop(topic, None)

    def add_topic(self, topic, reader):
        """Add named topic with desired reader.

        :param topic:    String name of topic to add.

        :param reader:   Either a string indicating something in
                         self.config.readers or an instance of OxLogReader.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  String message indicating success or KeyError if the
                  string in reader is not one we know about in self.config.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Add a topic that we want to keep track of.
        """
        try:
            reader = self.config.lookup_reader(reader)
        except KeyError as problem:
            return str(problem)

        self.config.topics[topic] = {
            'subscribed_at': datetime.datetime.utcnow(),
            'reader': reader,
            }
        return 'Added reader topic %s with reader %s' % (topic, reader.name())

    def refresh(self, force_raise=False):
        """Refresh data by re-loading all the logs.

        :param force_raise=False:   If True, raise an error if any exceptions
                                    are encountered. Otherwise, note the
                                    exceptions in self.cache['problems'] but
                                    don't stop processing.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Go through everything in self.config.topics and load
                  data for those logs. Any problems encountered are stored
                  in the form (TOPIC, PROBLEM) and can be returned by
                  self.get_problems().

        """
        problems = []
        for topic in self.config.topics:
            try:
                reader = self.config.load_reader(topic)
                my_data = reader.read(topic=topic)
                self.cache['topics'][topic] = my_data
            except Exception as bad:  # pylint: disable=broad-except
                problems.append((topic, str(bad)))
                if force_raise:
                    raise
        self.cache['last_updated_utc'] = datetime.datetime.utcnow()
        self.cache['problems'] = problems

    def get_problems(self):
        """Return list of problems encountered in last call to refresh

Resulting list is a list of pairs of the form (TOPIC, PROBLEM) where
TOPIC is the string name of the topic and PROBLEM is a string describing
the exception encountered when trying to call read for that topic.
        """
        return list(self.cache['problems'])
