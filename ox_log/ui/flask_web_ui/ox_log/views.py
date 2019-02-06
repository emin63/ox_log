"""Views for ox_log blueprint.
"""

import datetime

from flask import render_template, request

from flask_login import login_required

from ox_log.ui.flask_web_ui.ox_log import OX_LOG_BP, core
from ox_log.core import loader, utils


@OX_LOG_BP.route('/')
@OX_LOG_BP.route('/home')
@login_required
def home():
    return render_template('ox_log_home.html')


@OX_LOG_BP.route('/dashboard')
@login_required
def dashboard():
    max_items = request.args.get('max_items', '').strip()
    re_filter = request.args.get('re_filter', '.*').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    log_data = {}
    for topic, data in OX_LOG_BP.ox_log_loader.cache['topics'].items():
        log_data[topic] = utils.log_data_to_list(
            data, max_items, re_filter, utils.parse_date(start_date),
            utils.parse_date(end_date))
    ox_log_problems = OX_LOG_BP.ox_log_loader.get_problems()
    return render_template(
        'show_ox_log_data.html', log_data=log_data, start_date=start_date,
        end_date=end_date, max_items=max_items, re_filter=re_filter,
        ox_log_problems=ox_log_problems)


@OX_LOG_BP.route('/add_topic')
@login_required
def add_topic():
    topic = request.args.get('topic', '').strip()
    reader = request.args.get('reader', '').strip()    
    if not topic:
        return render_template('add_topic_form.html', known_readers={
            n: (r if isinstance(r, str) else r.describe())
            for n, r in OX_LOG_BP.ox_log_loader.config.readers.items()})
    result = OX_LOG_BP.ox_log_loader.add_topic(topic, reader)
    return render_template('ox_log_display.html', commentary=result)


@OX_LOG_BP.route('/drop_topic')
@login_required
def drop_topic():
    topic = request.args.get('topic', '').strip()
    if not topic:
        return render_template('drop_topic_form.html', topics=list(
            OX_LOG_BP.ox_log_loader.config.topics))

    OX_LOG_BP.ox_log_loader.drop_topic(topic)
    result = 'Removed topic "%s"' % topic

    return render_template('ox_log_display.html', commentary=result)


@OX_LOG_BP.route('/refresh')
@login_required
def refresh():
    "Refresh cached data."
    previous = OX_LOG_BP.ox_log_loader.cache['last_updated_utc']
    OX_LOG_BP.ox_log_loader.refresh()
    cur = OX_LOG_BP.ox_log_loader.cache['last_updated_utc']

    commentary = '\n'.join([
        'Cache Refreshed',
        'Previous update was %s; latest update is at %s' % (previous, cur)
        ])
    ox_log_problems = OX_LOG_BP.ox_log_loader.get_problems()

    return render_template('ox_log_display.html', commentary=commentary,
                           ox_log_problems=ox_log_problems)


def register(my_app, url_prefix='/ox_log', topics=None, readers=None):
    my_app.register_blueprint(OX_LOG_BP, url_prefix=url_prefix)
    config = loader.LoaderConfig(topics=topics, readers=readers)
    OX_LOG_BP.set_ox_log_config(config)
