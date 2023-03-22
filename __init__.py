import sys

# that might be rather a hack, but it keeps the imports from happening if the workers are imported by
# the mcpworker. They are supposed to run only when this is loaded as a plugin.

if "mcpcore.mcpworker" not in sys.modules:
    from kioskmenuitem import KioskMenuItem
    from core.kioskcontrollerplugin import KioskControllerPlugin

    from .pointrepositorycontroller import pointrepository
    from .pointrepositorycontroller import pointrepository_index
    from .pointrepositorycontroller import plugin_version

    # from authorization import MODIFY_DATA

    plugin: KioskControllerPlugin = None


    def instantiate_plugin_object(name, package, init_plugin_configuration={}):
        return KioskControllerPlugin(name, package, plugin_version=plugin_version)


    def init_app(app):
        app.register_blueprint(pointrepository)

    def register_plugin_instance(plugin_to_register):
        global plugin
        plugin = plugin_to_register


    def all_plugins_ready():
        global plugin
        return


    def register_index(app):
        app.add_url_rule('/', 'get_index', pointrepository_index)


    def register_menus():
        global plugin
        return [KioskMenuItem(name="point repository",
                              onclick="triggerModule('pointrepository.pointrepository_show')",
                              endpoint="pointrepository.pointrepository_show",
                              menu_cfg=plugin.get_menu_config(),
                              is_active=lambda:True,
                              ),
                ]

    def register_global_scripts():
        return {}
        # return {"pointrepository": ["pointrepository.static", "scripts/pointrepository.js", "async"]}
