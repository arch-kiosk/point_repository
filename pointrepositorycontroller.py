import datetime
import logging
import os
import pprint
from collections import namedtuple
from http import HTTPStatus

from flask import Blueprint, redirect, render_template, url_for, request, session, abort, make_response, send_file, \
    jsonify
from flask_allows import requires
from flask_login import current_user

import kioskdatetimelib
import kioskglobals
import kioskstdlib
from authorization import MODIFY_DATA, MANAGE_SERVER_PRIVILEGE, \
    IsAuthorized, is_authorized, get_local_authorization_strings
from authorization import full_login_required
from core.kioskcontrollerplugin import get_plugin_for_controller
from dsd.dsd3singleton import Dsd3Singleton
from kioskconfig import KioskConfig
from kiosklib import is_ajax_request
from kioskresult import KioskResult
from kiosksqldb import KioskSQLDb
from kioskuser import KioskUser
from orm.dsdtable import DSDTable
from plugins.kioskfilemakerworkstationplugin.kioskfilemakerworkstationcontroller import check_ajax
from pointimporter import PointImporter

_plugin_name_ = "pointrepositoryplugin"
_controller_name_ = "pointrepository"
_url_prefix_ = '/' + _controller_name_
plugin_version = 1

LOCAL_PRIVILEGES = {
    MODIFY_DATA: "modify data",
    MANAGE_SERVER_PRIVILEGE: "manage server",
}

pointrepository = Blueprint(_controller_name_, __name__,
                            template_folder='templates',
                            static_folder="static",
                            url_prefix=_url_prefix_)
print(f"{_controller_name_} module loaded")

pointrepository_controller = Blueprint(_controller_name_, __name__)
print(f"{_controller_name_} loaded")


@pointrepository.context_processor
def inject_current_plugin_controller():
    return dict(current_plugin_controller=get_plugin_for_controller(_plugin_name_))


def get_plugin_config():
    return kioskglobals.cfg.get_plugin_config(_plugin_name_)


#  **************************************************************
#  ****    redirecting index
#  *****************************************************************/

@pointrepository.route('_redirect', methods=['GET'])
@full_login_required
def pointrepository_index():
    print("------------- redirecting")
    return redirect(url_for("pointrepository.pointrepository_show"))


#  **************************************************************
#  ****    /pointrepository index
#  *****************************************************************/

@pointrepository.route('', methods=['GET', 'POST'])
@full_login_required
# @requires(IsAuthorized(ENTER_ADMINISTRATION_PRIVILEGE))
# @nocache
def pointrepository_show():
    class Header:
        def __init__(self, caption, sort, extra_caption=""):
            self.caption = caption
            self.extra_caption = extra_caption
            self.sort = sort

    class Point:
        def __init__(self, category, name, modified, longitude, latitude, elevation):
            self.category = category
            self.name = name
            self.modified = modified if modified else "-"
            self.latin_date = kioskstdlib.latin_date(self.modified) if modified else "-"
            self.longitude = longitude if longitude else "-"
            self.latitude = latitude if latitude else "-"
            self.elevation = elevation if elevation else "-"

    conf = kioskglobals.cfg

    print("\n*************** pointrepository/ ")
    print(f"\nGET: get_plugin_for_controller returns {get_plugin_for_controller(_plugin_name_)}")
    print(f"\nGET: plugin.name returns {get_plugin_for_controller(_plugin_name_).name}")

    authorized_to = get_local_authorization_strings(LOCAL_PRIVILEGES)
    conf = kioskglobals.cfg
    cfg = get_plugin_config()
    max_upload_size_mb = int(kioskstdlib.try_get_dict_entry(cfg, "max_upload_size_mb", "10"))

    if request.method == 'GET':
        sort_by = 'point name'
        sort_order = 'asc'
    else:
        sort_by = request.form["sort-by"]
        sort_order = request.form["sort-order"]

    authorized_to = get_local_authorization_strings(LOCAL_PRIVILEGES)

    modify_privilege = is_authorized(MODIFY_DATA)

    coordinates = DSDTable(Dsd3Singleton.get_dsd3(), "coordinates")
    points = []
    if sort_by == "point name":
        order_by = "coordinate_name"
    else:
        order_by = sort_by
    if sort_order != "asc":
        order_by += " DESC"
    if sort_by != "point name":
        order_by += ", coordinate_name"

    for c in coordinates.get_many(order_by=order_by):
        points.append(Point(c.category, c.coordinate_name, c.modified, c.longitude, c.latitude, c.elevation))

    headers = [Header('category', ''),
               Header('point name', ''),
               Header('modified', ''),
               Header('latitude', ''),
               Header('longitude', ''),
               Header('elevation', '')
               ]
    for header in headers:
        if header.caption == sort_by:
            header.sort = "fa-sort-up" if sort_order == "asc" else "fa-sort-down"

    return render_template('pointrepository.html',
                           authorized_to=authorized_to,
                           points=points,
                           headers=headers,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           modify_privilege=modify_privilege,
                           max_upload_size_mb=max_upload_size_mb)


#  **************************************************************
#  ****    UPLOAD FILE
#  *****************************************************************/
@pointrepository.route('/upload', methods=['POST'])
@full_login_required
@requires(IsAuthorized(MODIFY_DATA))
def pointrepository_upload():
    print(f"\n*************** pointrepository/upload")
    logging.info(f"pointrepositorycontroller.pointrepository_upload: attempt to upload a file")
    try:

        result = KioskResult(message="Unknown error after upload")
        logging.info(
            f"pointrepositorycontroller.pointrepository_upload: Received file from user {current_user.user_id}")

        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                logging.info(f"pointrepositorycontroller.pointrepository_upload: Received file {file.filename}")
                filename = kioskstdlib.get_filename(file.filename)

                rc, err = import_points(file, filename)
                if not rc:
                    result.message = f'The file {filename} was uploaded correctly but an error occurred ' \
                                     f'when importing the coordinates: {err}'
                else:
                    result.success = True
                    result.message = "file successfully uploaded."
            else:
                result.success = False
                result.message = "Either file or filename is empty."
        else:
            result.success = False
            result.message = "No uploaded file detected."

        return result.jsonify()
    except Exception as e:
        logging.error(f"pointrepository.pointrepository_upload: {repr(e)}")
        abort(HTTPStatus.INTERNAL_SERVER_ERROR, repr(e))


def import_points(file, filename: str) -> (bool, str):
    def update_coordinates(row: dict):
        sql = "INSERT INTO "
        sql += f"""coordinates ("coordinate_name","category", "description", "longitude", 
        "latitude", "elevation", "modified", "modified_by")
        """
        coordinates = DSDTable(dsd, "coordinates")
        if coordinates.get_one(f"coalesce(category,'')=%s and coordinate_name=%s",
                               [row['category'], row['point_name']]):
            if "longitude":
                if "longitude" in row:
                    coordinates.longitude = row["longitude"]
                if "latitude" in row:
                    coordinates.latitude = row["latitude"]
                if "elevation" in row:
                    coordinates.elevation = row["elevation"]
                if "description" in row:
                    coordinates.description = row["description"]
                coordinates.modified_by = current_user.repl_user_id
                coordinates.modified = kioskdatetimelib.get_utc_now(no_tz_info=True, no_ms=True)
                coordinates.modified_tz = current_user.get_active_tz_index()
                coordinates.modified_ww = current_user.get_utc_as_user_timestamp(coordinates.modified)
                coordinates.update()
        else:
            coordinates.category = row["category"]
            coordinates.coordinate_name = row["point_name"]
            coordinates.longitude = row["longitude"] if "longitude" in row else None
            coordinates.latitude = row["latitude"] if "latitude" in row else None
            coordinates.elevation = row["elevation"] if "elevation" in row else None
            coordinates.description = row["description"] if "description" in row else ""
            coordinates.modified_by = current_user.repl_user_id
            coordinates.modified = kioskdatetimelib.get_utc_now(no_tz_info=True, no_ms=True)
            coordinates.modified_tz = current_user.get_active_tz_index()
            coordinates.modified_ww = current_user.get_utc_as_user_timestamp(coordinates.modified)
            coordinates.add()

    cfg: KioskConfig = kioskglobals.get_config()
    dsd = Dsd3Singleton.get_dsd3()
    temp_dir = cfg.get_temporary_upload_path()
    dest_file = os.path.join(temp_dir, filename)
    file.save(dest_file)
    point_importer = PointImporter(dest_file, get_plugin_config())
    try:
        point_importer.load(update_coordinates)
        KioskSQLDb.commit()
        logging.debug(f"pointrepositorycontroller.import_points: import committed.")
        return True, ''
    except BaseException as e:
        KioskSQLDb.rollback()
        logging.error(f"pointrepositorycontroller.import_points: import rolled back because of {repr(e)}")
        return False, repr(e)
