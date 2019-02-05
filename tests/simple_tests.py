"""Some simple tests for ox_log.
"""

import doctest


def _regr_doctest_file_reader():
    """The following shows how you can test ox_log with a simple logfile.

This doctest illustrates how we can use ox_log as a very lightweight
log visualizer. Of course, we need a log to visualize. In this case,
we will configure the python logging handler to write a log file.

>>> import logging, tempfile
>>> logger = logging.getLogger('ox_log_test')
>>> logger.setLevel(logging.INFO)
>>> log_file = tempfile.mktemp(suffix='_eyap_log.txt')
>>> fh = logging.FileHandler(log_file)
>>> formatter = logging.Formatter('%(asctime)s|%(name)s|%(message)s')
>>> fh.setFormatter(formatter)
>>> logger.addHandler(fh)
>>> logger.info('Example message 1')
>>> logger.info('Example message 2')
>>> fh.flush()
>>> print(open(log_file).read().rstrip())  # doctest: +ELLIPSIS
2...|ox_log_test|Example message 1
2...|ox_log_test|Example message 2


Now we setup ox_log. We want to tell it to use the FileReader for
the given logfile.

>>> from ox_log.core import loader
>>> readers = {'my_file_log': loader.FileReader()}
>>> lconf = loader.LoaderConfig(readers)
>>> my_loader = loader.LogLoader(lconf)
>>> my_loader.add_topic(log_file, 'my_file_log') # doctest: +ELLIPSIS
'Added reader topic ..._eyap_log.txt with reader FileReader'

Finally, we are ready to visualize the log data. First we need to
refresh the cache so that ox_log pulls in data from the log and then
we can display it.

>>> my_loader.refresh()  # Refresh data from logs we watch
>>> list(my_loader.cache['topics'])  # doctest: +ELLIPSIS
['..._eyap_log.txt']
>>> for topic, data in my_loader.cache['topics'].items():
...     for item in data:
...         msg = '%s | %s | %s' % (item.timestamp, item.summary, item.body)
...         print(msg)  # doctest: +ELLIPSIS
...
2... | ox_log_test | Example message 1
2... | ox_log_test | Example message 2

Now cleanup.

>>> os.remove(log_file)
>>> os.path.exists(log_file)
False
"""

    def _regr_test_eyap():
        """The following shows how you can test ox_log using eyap.

The eyap package is a very lightweight comment management tool. In this
example, we setup a comment thread with a file backend and write a few
message which we will leader visualize using ox_log. The eyap package
has other backends as well which you can use in a similar way.


>>> import os, logging, tempfile, shutil, eyap
>>> eyap_kwargs = {'backend': 'file', 'owner': 'ox_log_test',
...     'realm': tempfile.mkdtemp(prefix='ox_log_test_', suffix='_eyap_log')}
>>> eyap_log = eyap.Make.comment_thread(topic='test_log', **eyap_kwargs)
>>> eyap_log.add_comment('foobar', summary='Example Note 1', allow_create=True)
>>> eyap_log.add_comment('more', summary='Example Note 2', allow_create=True)

Now we setup ox_log. We want to tell it we have a reader.

>>> from ox_log.core import loader
>>> readers = {'my_eyap': loader.EyapReader(**eyap_kwargs)}
>>> topics = {}
>>> lconf = loader.LoaderConfig(topics=topics, readers=readers)
>>> my_loader = loader.LogLoader(lconf)
>>> my_loader.add_topic('test_log', 'my_eyap')
'Added reader topic test_log with with reader EyapReader'
>>> my_loader.refresh()  # Refresh data from logs we watch
>>> list(my_loader.cache['topics'])  # Show known topics
['test_log']
>>> for item in my_loader.cache['topics']['test_log']:
...     msg = '%s: %s: %s' % (item.timestamp, item.summary, item.body)
...     print(msg)  # doctest: +ELLIPSIS
...
2...: Example Note 1: foobar
2...: Example Note 2: more

Now cleanup.

>>> shutil.rmtree(eyap_kwargs['realm'])
>>> os.path.exists(eyap_kwargs['realm'])
False
"""

if __name__ == '__main__':
    doctest.testmod()
    print('Finished Tests')
