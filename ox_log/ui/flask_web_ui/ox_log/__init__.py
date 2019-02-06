"""Flask blueprint for ox_log.
"""

from flask import Blueprint

from ox_log.core import loader


class OxLogBlueprint(Blueprint):
    """Flask blueprint to provide lightweight log analysis.
"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ox_log_loader = loader.LogLoader()

    def set_ox_log_config(self, config):
        """Take as input an ox_log LoaderConfig and load into the blueprint.
"""
        self.ox_log_loader.set_config(config)


OX_LOG_BP = OxLogBlueprint(
    'ox_log', __name__, template_folder='templates', static_folder='static')
