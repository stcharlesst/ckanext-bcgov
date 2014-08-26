'''
    Important : When importing discovery and odsi records, two files with names
    discovery_record_count.txt and odsi_record_count.txt are created which simply contain
    the number of records have been already imported. If you rerun the scripts, they wont re-import
    records that have been already imported unless these files are deleted. Having these files, is also necessary to
    import the remaining records in case of a data import error.
'''

import cx_Oracle
import urllib2
import urllib
import os
import json
import pprint
import re
import getpass

import datetime

from ckanext.edc_schema.commands.base import edc_package_create

from ckanext.edc_schema.util.util import (get_organization_id,
                                          get_user_id)

admin_user = 'kmamakani'
#admin_user = 'khalegh'
#admin_user = 'admin'


def is_valid_url(url):
    import urlparse
    import string

    if not url:
        return True

    pieces = urlparse.urlparse(url)
    if all([pieces.scheme, pieces.netloc]) and \
        set(pieces.netloc) <= set(string.letters + string.digits + '-.') and \
        pieces.scheme in ['http', 'https']:
        return True

    #Invalid url is given
    return False

def get_record_list():

    from ckanext.edc_schema.commands.base import (site_url, api_key)
    '''
    Returns the list of available records
    Records that have been already imported.
    '''
    try:
        request = urllib2.Request(site_url + '/api/3/action/package_list?limit=1000000')
        request.add_header('Authorization', api_key)
        response = urllib2.urlopen(request)
        assert response.code == 200

        # Use the json module to load CKAN's response into a dictionary.
        response_dict = json.loads(response.read())
        assert response_dict['success'] is True

        #package_create returns the created package as its result.
        pkg_list = response_dict['result']
    except Exception, e:
        pkg_list = []

    return pkg_list

def remove_invalid_chars(name):
    name = re.sub('[^0-9a-zA-Z]+',' ', name)
    name = ' '.join(name.split())
    return name

def get_record_name(pkg_list, title):
    '''
    Returns a unique record name based on the given record title.
    Constructs the package name given the package title.
    Searches the package name in the available packages list
    and adds the sequence number if they are packages with the same name.
    '''

#    print 'Package title : ', title
    #Replace all characters other that 0-9, a-z, A-Z with space
    name = re.sub('[^0-9a-zA-Z]+',' ', title)
    name = ' '.join(name.split())

    #Remove extra white spaces and replace spaces with '-'
    name = name.lower().strip().replace(' ', '-')

    #Truncate the title, it cannot hav emore that 100 characters
    if len(name) > 100 :
        name = name[:100]

    '''
    Compute the total number of records imported with the same.
    Get the record base name( name without the record count)
    '''
    count = 0

    index = min(len(name), 96)
    base_name = name[:index]

    if (len(name) >= 4) and (name[-4] == '-') :
        count_str = name[-3:]
        if count_str.isdigit() :
            count = int(count_str)
            base_name = name[:-4]

    while (name in pkg_list) :
        count += 1
        name = base_name + ("-%03d" % (count,))

#    print 'package name :', name
    return name


def get_connection(data_source):

    if data_source.lower() == 'odc' :
#         host = 'sponde.bcgov'
#         port = 1521
#         SID = 'idwprod1.bcgov'
#         user_name = 'proxy_metastar'
#         password = 'h0tsh0t'
        connection_str = "proxy_metastar/h0tsh0t@slkux1.env.gov.bc.ca/idwprod1.bcgov"
        con = cx_Oracle.connect(connection_str)
    elif data_source.lower() == 'discovery' :
         user_name = 'metastar'
         host = 'slkux12.env.gov.bc.ca'
         port = 1521
         SID = 'BCGWDLV'
         password = 'blueb1rd'
         dsn_tns = cx_Oracle.makedsn(host, port, SID)
         con = cx_Oracle.connect(user_name, password, dsn_tns)
#        connection_str = "proxy_metastar/h0tsh0t@slkux1.env.gov.bc.ca/idwprod1.bcgov"
    else :
        print "No data source is given."

#    password = getpass.getpass("Password:")



#    con = cx_Oracle.connect(connection_str)

    return con

def execute_odsi_query(con):
    '''
    Fetches ODSI records from datbase
    '''
    edc_auery = "SELECT DBC_RS.RESOURCE_SET_ID RESOURCE_SET_ID " + \
                ",DBC_CO.CREATOR_ORGANIZATION CREATOR_ORGANIZATION " + \
                ",DBC_RS.TITLE TITLE " + \
                ",DBC_RS.DESCRIPTION DESCRIPTION " + \
                ",DBC_RS.KEYWORDS KEYWORDS " + \
                ",DBC_RS.SOURCE_CITATION SOURCE_CITATION " + \
                ",DBC_SO.SUB_ORGANIZATION SUB_ORGANIZATION " + \
                ",DBC_RS.TEMPORAL_COVERAGE TEMPORAL_COVERAGE " + \
                ",DBC_RT.RESOURCE_TYPE_NAME RESOURCE_TYPE_NAME " + \
                ",DBC_RS.FEATURE_CLASS_NAME FEATURE_CLASS_NAME " + \
                ",DBC_LT.LICENSE_TYPE_ID LICENSE_ID " + \
                ",DBC_MP.LAYER_NAME MAP_PREVIEW_LAYER_NAME " + \
                ",DBC_MP.LATITUDE MAP_PREVIEW_LATITUDE " + \
                ",DBC_MP.LONGITUDE MAP_PREVIEW_LONGITUDE " + \
                ",DBC_MP.ZOOM_LEVEL MAP_PREVIEW_ZOOM_LEVEL " + \
                ",DBC_MP.SERVICE_URL MAP_PREVIEW_SERVICE_URL " + \
                ",TO_CHAR(DBC_RS.DATE_MODIFIED, 'YYYY-MM-DD')  AS DATE_MODIFIED " + \
                ",TO_CHAR(DBC_RS.DATE_PUBLISHED, 'YYYY-MM-DD')  AS DATE_PUBLISHED " + \
                ",TO_CHAR(DBC_RS.DATE_ADDED, 'YYYY-MM-DD')  AS DATE_ADDED" + \
                ",DBC_DC.DISPLAY_NAME " + \
                ",DBC_DC.DISPLAY_EMAIL " + \
                ",DBC_RS.RESOURCE_STATE " + \
                ",DBC_RS.DISCOVERY_UID DISCOVERY_ID " + \
                "FROM APP_DATABC.DBC_RESOURCE_SETS DBC_RS " + \
                ",APP_DATABC.DBC_CREATOR_ORGANIZATIONS DBC_CO " + \
                ",APP_DATABC.DBC_CREATOR_SECTORS DBC_CS " + \
                ",APP_DATABC.DBC_LICENSE_TYPES DBC_LT " + \
                ",APP_DATABC.DBC_MAP_PREVIEWS DBC_MP " + \
                ",APP_DATABC.DBC_RESOURCE_TYPES DBC_RT " + \
                ",APP_DATABC.DBC_SUB_ORGANIZATIONS DBC_SO "+ \
                ",APP_DATABC.DBC_DISPLAY_CONTACTS DBC_DC " + \
                ",(select RESOURCE_SET_ID,min(DISPLAY_CONTACT_ID) DISPLAY_CONTACT_ID from APP_DATABC.DBC_DISPLAY_CONTACTS " + \
                "group by RESOURCE_SET_ID) DBC_Dc_MIN " + \
                "WHERE DBC_RS.SUB_ORGANIZATION_ID=DBC_SO.SUB_ORGANIZATION_ID " + \
                "AND DBC_CO.CREATOR_ORGANIZATION_ID=DBC_SO.CREATOR_ORGANIZATION_ID " + \
                "AND DBC_LT.LICENSE_TYPE_ID=DBC_RS.LICENSE_TYPE_ID " + \
                "AND DBC_MP.RESOURCE_SET_ID(+)=DBC_RS.RESOURCE_SET_ID " + \
                "AND DBC_RT.RESOURCE_TYPE_ID=DBC_RS.RESOURCE_TYPE_ID " + \
                "AND DBC_CS.CREATOR_SECTOR_ID=DBC_SO.CREATOR_SECTOR_ID " + \
                "AND DBC_DC_MIN.RESOURCE_SET_ID(+)=DBC_RS.RESOURCE_SET_ID " + \
                "AND DBC_DC.DISPLAY_CONTACT_ID(+)=DBC_DC_MIN.DISPLAY_CONTACT_ID " #+\
#                "AND DBC_RT.RESOURCE_TYPE_NAME ='Geospatial Dataset'" #+ \
#                "AND DBC_RS.RESOURCE_SET_ID = 178047 "


    cur = con.cursor()
    cur.execute(edc_auery)
    data = cur.fetchall()

    return data

def import_odc_records(con):

    from validate_email import validate_email

    user_id = get_user_id(admin_user)
#    print user_id


    #Get the list of available records
    pkg_list = get_record_list()


    #Get the number of discovery records have already been imported.
    record_count_filename = 'odsi_record_count.txt'
    if not os.path.exists(record_count_filename):
        previous_count = 0
    else :
        with open(record_count_filename, 'r') as record_count_file :
            previous_count = int(record_count_file.read())
    print previous_count

    #Load data for discovery records available in ODSI
    with open('discovery_ODSI.json', 'r') as discovery_file :
        discovery_data = json.loads(discovery_file.read())

    #Fetch raw records.
    data = execute_odsi_query(con)

    total_number_of_records = len(data)

    index = 0
    records_created = 0

    #Create ODSI error file
    error_file = open('ODSI_errors.txt', 'a')

#    for result in data:
    for result in data:
        try:
            if index < previous_count :
                index += 1
                continue

            edc_record = {}

            #------------------------------------------------------------------< Discovery Records >------------------------------------------------------------------
            # Get Discovery info if the records has metastar_uid
            if result[22] :
                if str(result[22]) in discovery_data :
                    discovery_record = discovery_data[str(result[22])]

            #-------------------------------------------------------------------< Dataset State >---------------------------------------------------------------------
            edc_record['edc_state'] = result[21] or 'DRAFT'

            #Ignore DRAFT records or records with no title
            if (not result[2]) or edc_record['edc_state'] == 'DRAFT':
                index += 1
                continue

            #Do not import Theme records
            if '(Theme)' in result[2] :
                index += 1
                continue

            #********** Note : this is temporary. ************
            #Drop records from Ministry of Health, British Columbia Vital Statistics Agency
            if (result[1] == 'Ministry of Health') and  (result[6] == 'British Columbia Vital Statistics Agency') :
                index += 1
                continue

            #---------------------------------------------------------------< Dataset name and Title >-------------------------------------------------------------------
            title = result[2]

            #Remove (DEPRECATED) from the record title
            if title.startswith('(DEPRECATED) ') :
                title = title.replace('(DEPRECATED) ', '').strip()
                edc_record['notes'] = 'DEPRECATED - The resource(s) that this record refers is obsolete and may be scheduled for retirement. Please see the Replacement Record reference in the Data Currency / Update section.'
            else :
            #---------------------------------------------------------------------< Dataset Description >---------------------------------------------------------------------
                edc_record['notes'] = result[3] or ' '



            edc_record['name'] = get_record_name(pkg_list, title);
            edc_record['title'] = title


            #-------------------------------------------------------------------< Dataset License >---------------------------------------------------------------------
            license_id = str(result[10])

            if license_id == '1' :
                edc_record['license_id'] = '2'
            elif license_id == '2' :
                edc_record['license_id'] = '21'
            elif  license_id == '3' or license_id == '4' :
                edc_record['license_id'] = '22'
            elif  license_id == '5':
                edc_record['license_id'] = '24'
            else :
                edc_record['license_id'] = '41'



            #-----------------------------------------------------------------------< Dataset Type >-----------------------------------------------------------------------
            # Setting the record type
            type_dict = {'Application' : 'Application', 'Geospatial Dataset' : 'Geographic', 'Non-Geospatial Dataset' : 'Dataset', 'Web Service' : 'WebService'}
            edc_record['type'] = type_dict[result[8]]

            #----------------------------------------------------------------------< Dataset Author >-----------------------------------------------------------------------
            edc_record['author'] = user_id

            #------------------------------------------------------------------< Dataset Organization >---------------------------------------------------------------------
            org = get_organization_id(result[1])
            edc_record['org'] = org
            edc_record['sub_org'] = get_organization_id(result[6])
            edc_record['owner_org'] = edc_record['sub_org'] or edc_record['org']

            #----------------------------------------------------------------------< Dataset Keywords >----------------------------------------------------------------------
            if result[4]:
                # Extract the keywords(tags) names and add the list of tags to the record.
                keywords = result[4].split(',')
                edc_record['tags'] = [{'name' : remove_invalid_chars(keyword).strip()} for keyword in keywords if keyword and len(keyword) > 1]



            #-----------------------------------------------------------------< Dataset dates >-------------------------------------------------------------------
            dates = []

            if result[18] :
                dates.append({'type': 'Created', 'date': result[18], 'delete': '0'})
            else :
                #Add today as dataset creation date
                dates.append({'type': 'Created', 'date': str(datetime.date.today()), 'delete': '0'})

            if result[16] :
                dates.append({'type': 'Modified', 'date': result[16], 'delete': '0'})

            if result[17] :
                dates.append({'type': 'Published', 'date': result[17], 'delete': '0'})
                #Adding record publish date
                edc_record['publish_date'] = result[17]
                edc_record['record_publish_date'] = result[17]

            elif edc_record['edc_state'] == 'Published' :
                edc_record['publish_date'] = str(datetime.date.today())
                edc_record['record_publish_date'] = str(datetime.date.today())

            edc_record['dates'] = dates

            #-----------------------------------------------------------------< Dataset Contacts >----------------------------------------------------------------
            if result[20] and validate_email(result[20]) :
                contact_email = result[20]
            else:
                contact_email = 'databc@gov.bc.ca'

            contact_name = result[19] or 'DataBC Operations'
            contacts = []
            contacts.append({'name': contact_name, 'email': contact_email, 'delete': '0', 'organization': org, 'role' : 'pointOfContact', 'private' : 'Display'})

            edc_record['contacts'] = contacts

            odsi_uid_str = ''
            if result[0] :
                odsi_uid_str = str(result[0])
            edc_record['odsi_uid'] = odsi_uid_str


            #----------------------------------------------------------< Dataset more info >--------------------------------------------------------------------
            more_info_link = None
            #To Do : Check if the link provided is valid, otherwise set it to null.
            if result[5] and is_valid_url(result[5]) :
                more_info_link = result[5]
            edc_record['more_info'] = [{'link': more_info_link, 'delete': '0'}]


            #----------------------------------------------------------< Dataset map preview >--------------------------------------------------------------------
            if edc_record['type'] == 'Geographic':
                map_layer_name = result[11]
                if map_layer_name and map_layer_name != 'DBM_7H_MIL_POLITICAL_POLY_BC':
                    edc_record['layer_name'] = result[11]
                    edc_record['preview_latitude'] = result[12]
                    edc_record['preview_longitude'] = result[13]
                    edc_record['preview_zoom_level'] = result[14]
                    map_service_url = result[15]
                    map_server_url = 'http://openmaps.gov.bc.ca/mapserver/'
                    if not is_valid_url(map_service_url) :
                        map_service_url = map_server_url + map_service_url
                    edc_record['preview_map_service_url'] = map_service_url


            #----------------------------------------------------------< Dataset Object name >--------------------------------------------------------------------
            if (edc_record['type'] == 'Geographic') and result[9]:
                object_name = result[9]
                if (object_name.startswith('WHSE_') or object_name.startswith('REG_')) :
                    edc_record['object_name'] = object_name


            '''
            Update record data if it is available in discovery.
            '''
            if result[22] and discovery_record :
                edc_record['resource_status'] = discovery_record['resource_status']

                edc_record['security_class'] = discovery_record['security_class']

                edc_record['view_audience'] = discovery_record['view_audience']

                edc_record['download_audience'] = discovery_record['download_audience']

                edc_record['metadata_visibility'] = discovery_record['metadata_visibility']

                edc_record['privacy_impact_assessment'] = discovery_record['privacy_impact_assessment']

                edc_record['iso_topic_cat'] = discovery_record['iso_topic_cat']

                edc_record['spatial'] = discovery_record['spatial']

                edc_record['south_bound_latitude']  =  discovery_record['south_bound_latitude']

                edc_record['north_bound_latitude'] =   discovery_record['north_bound_latitude']

                edc_record['west_bound_longitude'] =   discovery_record['west_bound_longitude']

                edc_record['east_bound_longitude'] =  discovery_record['east_bound_longitude']

                edc_record['retention_expiry_date'] = discovery_record['retention_expiry_date']

                edc_record['source_data_path'] = discovery_record['source_data_path']

                edc_record['lineage_statement'] = discovery_record['lineage_statement']

                edc_record['archive_retention_schedule'] = discovery_record['archive_retention_schedule']

                edc_record['purpose'] =  discovery_record['purpose']

                edc_record['metadata_language'] = discovery_record['metadata_language']

                edc_record['metadata_character_set'] = discovery_record['metadata_character_set']

                edc_record['metadata_standard_name'] = discovery_record['metadata_standard_name']

                edc_record['metadata_standard_version'] = discovery_record['metadata_standard_version']


            else :

            #-----------------------------------------------------------------< Dataset resource status >----------------------------------------------------------
                edc_record['resource_status'] = 'completed'         #Default value : completed

            #-----------------------------------------------------------------< Dataset Constraints >----------------------------------------------------------
                edc_record['security_class'] = 'LOW-PUBLIC'          #Default value : LOW-PUBLIC

            # Set record view audience and download audience to public
                edc_record['view_audience'] = 'Public'           #Default value : public
                edc_record['download_audience'] = 'Public'       #Default value : public

                edc_record['metadata_visibility'] = 'Public'    #Default value : public

                edc_record['privacy_impact_assessment'] = 'Yes' #Default value : YES

                edc_record['iso_topic_cat'] = ['economy']          #Default value : economy

                edc_record['metadata_language'] = 'English'

                edc_record['metadata_character_set'] = 'utf8'

                edc_record['metadata_standard_name'] = 'North American Profile of ISO 19115-1:2014 - Geographic information - Metadata (NAP-Metadata)'

                edc_record['metadata_standard_version'] = 'n/a'


            record_id = result[0]

            resource_data = None
            if record_id :
                resource_query = "SELECT * FROM APP_DATABC.DBC_RESOURCE_ACCESS_ODC_VW WHERE RESOURCE_SET_ID = '" + str(record_id) + "'"
                resource_cur = con.cursor()
                resource_cur.execute(resource_query)
                resource_data = resource_cur.fetchall()

            resources = []
            for resource in resource_data:

                resource_rec = {}
                # Setting resource url to RESOURCE_ACCESS_URL from ODC
                resource_url = resource[3]
                resource_rec['url'] = resource_url

                resource_name = ''
                # Setting resource name to PRODUCT_TYPE_NAME frrom ODC
                if resource_url :
                    resource_name = resource_url.rsplit('/',1)[1]
                    if resource_name == 'addProductsFromExternalApplication':
                        resource_name = title #'External Resource'
                    resource_rec['name'] = resource_name

                #----------------------------------------------------------< Resource Format >--------------------------------------------------------------------
                res_format = ""
                resource_extension = os.path.splitext(resource_name)[1]
                if resource_extension and '.' in resource_extension :
                    resource_extension = resource_extension[1:]
                    res_format = resource_extension.upper()

                valid_formats = ["ATOM","CDED", "CSV", "E00", "FGDB", "GEOJSON",
                                "GEORSS", "HTML", "JSON", "KML", "KMZ", "PDF", "RDF",
                                "SHP", "TXT", "WMS", "XLS", "XLSX", "XML", "ZIP"]

                if res_format == "" or res_format not in valid_formats :
                    mimeType = (resource[1] or 'Unknown').lower()
                    if mimeType == 'application/zip' :
                        res_format = 'ZIP'
                    elif mimeType == 'application/json':
                        res_format = "JSON"
                    elif mimeType == 'application/xls' :
                        res_format = 'XLS'
                    elif mimeType == 'application/xml' or mimeType == 'application/rdf+xml':
                        res_format = 'XML'
                    elif mimeType == 'text/csv' :
                        res_format = 'CSV'
                    elif mimeType == 'text/plain' :
                        res_format = 'TXT'
                    elif mimeType == 'application/vnd.google-earth.kmz' or mimeType == 'application/vnd.google-earth.kml+xml' :
                        res_format = 'KMZ'
                    else:
                        res_format = 'Other'

                resource_rec['format'] = res_format

                # Setting Geospatial and Non-geospatial specific resource fields
                if edc_record['type'] == 'Geographic' or edc_record['type'] == 'Dataset':
            #----------------------------------------------------------< Resource Type >--------------------------------------------------------------------
                    resource_rec['edc_resource_type'] = 'Data'

            #----------------------------------------------------------< Resource storage access method >--------------------------------------------------------------------
                    resource_storage_access_method = resource[5] or 'Direct Access'
                    resource_rec['resource_storage_access_method'] = resource_storage_access_method.strip()

            #----------------------------------------------------------< Resource storage Location >--------------------------------------------------------------------
                    #Check the resourec url and set the resource storage location based on that :
                    res_url = resource[3]
                    if res_url :
                        if res_url.startswith('http://pub.data.gov.bc.ca/datasets') :
                            resource_rec['resource_storage_location'] = 'pub.data.gov.bc.ca'
                        elif res_url.startswith('https://apps.gov.bc.ca/pub/dwds') :
                            resource_rec['resource_storage_location'] = 'BCGW Data Store'
                        else :
                            resource_rec['resource_storage_location'] = 'External'


            #----------------------------------------------------------< Resource Projection Name >--------------------------------------------------------------------
                    if edc_record['type'] == 'Geographic':
                        projection_name = 'EPSG_4326 - WGS84 - World Geodetic System 1984'
                        resource_rec['projection_name'] = projection_name


            #-------------------------------------------------------------< Resource Update Cycle >--------------------------------------------------------------------
                # Set record's resource update cycle
                update_cycle = ''
                if result[7] :
                    update_cyle_str = result[7].lower()
                else:
                    update_cyle_str = 'monthly'

                if 'day' in update_cyle_str or 'daily' in update_cyle_str:
                    update_cycle = 'daily'
                elif 'week' in update_cyle_str:
                    update_cycle = 'weekly'
                elif 'fortnightly' in update_cyle_str:
                    update_cycle = 'fortnightly'
                elif 'month' in update_cyle_str:
                    update_cycle = 'monthly'
                elif 'quarterly' in update_cyle_str:
                    update_cycle = 'quarterly'
                elif 'semi-annually' in update_cyle_str or 'biannual' in update_cyle_str:
                    update_cycle = 'biannually'
                elif 'annual' in update_cyle_str or 'year' in update_cyle_str:
                    update_cycle = 'annually'
                elif 'needed' in update_cyle_str or 'as required' in update_cyle_str or 'as necessary' in update_cyle_str :
                    update_cycle = 'asNeeded'
                elif 'occasional' in update_cyle_str or 'irregular' in update_cyle_str:
                    update_cycle = 'irregular'
                elif 'notplanned' in update_cyle_str :
                    update_cycle = 'notPlanned'
                elif 'periodic' in update_cyle_str or 'continual' in update_cyle_str:
                    update_cycle = 'continual'
                else:
                    update_cycle = 'monthly'

                resource_rec['resource_update_cycle'] = update_cycle

                #Update resource data if the record is available in discovery
                if result[22] and discovery_record :
                    resource_rec['edc_resource_type'] = discovery_record['edc_resource_type']
                    resource_rec['resource_update_cycle'] = discovery_record['resource_update_cycle'] or 'monthly'
                    resource_rec['data_collection_start_date'] = discovery_record['data_collection_start_date']
                    resource_rec['data_collection_end_date'] = discovery_record['data_collection_end_date']

                # Add the current resource record to the list of dataset resources
                resources.append(resource_rec)

            # Add the list of dataset resources to the dataset
            edc_record['resources'] = resources

#            pprint.pprint(edc_record)

            (record_info, errors) = edc_package_create(edc_record)

            if  record_info :
                pkg_list.append(edc_record['name'])
                records_created += 1
                print '--------------------<< Record with uid %s is imported >>--------------------' % str(result[0])
            else :
                pprint.pprint(errors)

                error_file.write('Error in importing record with UID : ' + str(result[0]) + '\n')
                error_file.write('Record info :\n')
                json.dump(edc_record, error_file)
                error_file.write('\nError details :')
                json.dump(errors, error_file)
                error_file.write('\n\n------------------------------------------------------------------------------------------------------------------------------------\n\n')

            index = index + 1

        except Exception, e:
            print str(e)
            error_file.write('Exception in importing record with UID ' + odsi_uid_str) + '\n'
#             import traceback
#             print traceback.format_exc()
            pass

    con.close()

    #Save the number of ODSI records have been imported.
    with open('odsi_record_count.txt', 'w') as record_count_file :
        record_count_file.write(str(index))

    print "Total number of records : ", total_number_of_records
    print "Records created : ", records_created


#    save_record_dict(record_dict, "odsi_dict.json")


def get_organization(org_str):

    if not org_str :
        return (None, None)

    #Get the organization type code (BCGOV, BCAGENCY, NONGOV, MUNIC, ...)
    prefix = org_str.split(' ', 1)[0]
    prefix_len = len(prefix)

    org_code = ''
    org_titles = {
                    'AL' : 'Ministry of Agriculture',
                    'ARR': 'Ministry of Aboriginal Relations and Reconciliation',
                    'CSCD': 'Ministry of Community, Sport and Cultural Development',
                    'ED': 'Ministry of Education',
                    'EMPR': 'Ministry of Energy and Mines',
                    'ENV': 'Ministry of Environment',
                    'FLNRO': 'Ministry of Forests, Lands and Natural Resource Operations',
                    'FOR' : 'Ministry of Forests, Lands and Natural Resource Operations',
                    'HLS' : 'Ministry of Health',
                    'HLTH': 'Ministry of Health',
                    'ILMB': 'Integrated Land Management Bureau',
                    'JAG': 'Ministry of Justice',
                    'LCS': "Ministry of Technology, Innovation and Citizens Services",
                    'MEM': 'Ministry of Energy and Mines',
                    'MCFD': 'Ministry of Children and Family Development',
                    'MOT': 'Ministry of Transportation and Infrastructure',
                    'MSDSI': 'Ministry of Social Development and Social Innovation',
                    'NGD' : 'Ministry of Natural Gas Development',
                    'PSSG': 'Public Safety and Solicitor General',
                    'TCA': 'Ministry of Jobs, Tourism and Skills Training'
                }

    org_title = None
    sub_org_title = None

    if prefix == 'BCGOV':
        org_code = org_str.split(' ', 2)[1]
        org_title = org_titles[org_code]
        sub_org_index = len(org_code) + 7
        sub_org_title = org_str[sub_org_index:]
    elif prefix == 'CDNGOV':
        org_title = 'Government of Canada'
        sub_org_title =  org_str[7:]
    elif prefix == 'BCAGENCY':
        org_title = org_str[9:]
        if org_title and org_title.startswith('Agricultural Land Commission'):
            sub_org_title = org_title
            org_title = 'Ministry of Agriculture'
        elif org_title and org_title.startswith('Environmental Assessment Office'):
            sub_org_title = 'Environmental Assessment Office'
            org_title = 'Ministry of Environment'
        elif org_title and org_title.startswith('Elections British Columbia'):
            sub_org_title = 'Elections British Columbia'
            org_title = 'Ministry of Technology, Innovation and Citizens Services'
        elif org_title and org_title.startswith('Oil and Gas Commission') :
            sub_org_title = 'Oil and Gas Commission'
            org_title = 'Ministry of Natural Gas Development'
        else:
            sub_org_title = ''
    elif prefix == 'NONGOV' or prefix == 'MUNIC':
        org_title = org_str[prefix_len+1:]
        sub_org_title = ''
    elif prefix == 'OTHER':
        org_title = 'BC Government'
        sub_org_title = ''
    else :
        pass

    return (org_title, sub_org_title)


def load_common_records() :

    with open('common_records_titles.txt', 'r') as common_records_file :
        common_records_titles = [line.rstrip('\n') for line in common_records_file]

    with open('common_records_uids.txt', 'r') as common_records_file :
        common_records_uids = [line.rstrip('\n') for line in common_records_file]

    return (common_records_uids, common_records_titles)


def execute_discovery_query(con):
    '''
    Fetches the discovery records from database
    '''
    edc_query = "SELECT dat.sv_2 Title, " \
                "dat.xml_data.extract('//E9286/text()').getStringVal() Description, " \
                "SUBSTR(dat.xml_data.extract('//E9254/text()').getStringVal(),1,300) Data_Custodian_organization, " \
                "st.state_name, " \
                "dat.xml_data.extract('//E9288/text()').getStringVal() Purpose, " \
                "metastar.getKeywords(dat.record_uid) Keywords, " \
                "SUBSTR(dat.xml_data.extract('//E9292/text()').getStringVal(),1,105) Resource_Status, " \
                "metastar.getContactNames(dat.record_uid) Contact_Name, " \
                "metastar.getContactEmails(dat.record_uid) Contact_Email, " \
                "metastar.getContactOrganization(dat.record_uid) Contact_Organization, " \
                "dat.xml_data.extract('//E9342/text()').getStringVal() MAINT_FREQ_CODE, " \
                "SUBSTR(dat.xml_data.extract('//E11266/text()').getStringVal(),1,4) DataViewPubl, " \
                "SUBSTR(dat.xml_data.extract('//E11404/text()').getStringVal(),1,4) DataDistPubl, " \
                "SUBSTR(dat.xml_data.extract('//E11436/text()').getStringVal(),1,6) PIAComplete, " \
                "to_number(dat.RECORD_UID) RECORD_UID, " \
                "dat.xml_data.extract('//E9742/text()').getStringVal() Projection_Name, " \
                "to_char(to_date(dat.xml_data.extract('//E10000/text()').getStringVal(),'YYYY-MM-DD'), 'YYYY-MM-DD') Beginning_Date, " \
                "to_char(to_date(dat.xml_data.extract('//E10002/text()').getStringVal(),'YYYY-MM-DD'), 'YYYY-MM-DD') End_Date, " \
                "dat.xml_data.extract('//E9514/text()').getStringVal() Lineage_Statement, " \
                "SUBSTR(dat.xml_data.extract('//E10330/text()').getStringVal(),1,3) IS_PUBLIC, " \
                "dat.xml_data.extract('//E10338/text()').getStringVal() Archive_Retention_Schedule, " \
                "to_char(to_date(dat.xml_data.extract('//E10340/text()').getStringVal(),'YYYY-MM-DD'), 'YYYY-MM-DD') Retention_Expiry_Date, " \
                "dat.xml_data.extract('//E10348/text()').getStringVal() Source_Data_Path, " \
                "SUBSTR(dat.xml_data.extract('//E9866/text()').getStringVal(),1,105) Resource_Type, " \
                "SUBSTR(dat.xml_data.extract('//E10284/text()').getStringVal(),1,750) Resource_Storage_Location, " \
                "metastar.getFeatureClassNames(dat.record_uid) Feature_Class_Names, " \
                "metastar.getFeatureClassDescriptions(dat.record_uid) Feature_Class_Descriptions, " \
                "metastar.getOnlineReferences(dat.record_uid) Online_References, " \
                "SUBSTR(dat.xml_data.extract('//E9388/text()').getStringVal(),1,300) Classification_Category, " \
                "metastar.getIsoCategory(dat.record_uid) ISO_Topic_Category, " \
                "to_char(dat.record_createdate, 'YYYY-MM-DD')  CREATEDATE, " \
                "to_char(to_date(dat.xml_data.extract('//E9260/text()').getStringVal(),'YYYY-MM-DD'), 'YYYY-MM-DD') DATE_MODIFIED, " \
                "SUBSTR(dat.xml_data.extract('//E11282/text()').getStringVal(),1,3) License_data, " \
                "dat.xml_data.extract('//E9350/text()').getStringVal() Resource_Storage_Description, " \
                "dat.xml_data.extract('//E10050/text()').getStringVal() object_name, " \
                "SUBSTR(dat.xml_data.extract('//E9682/text()').getStringVal(),1,450) UNIQUE_METADATA_URL, " \
                "to_number(dat.xml_data.extract('//E9438/text()').getStringVal()) Extent_North, " \
                "to_number(dat.xml_data.extract('//E9436/text()').getStringVal()) Extent_South, " \
                "to_number(dat.xml_data.extract('//E9434/text()').getStringVal()) Extent_East, " \
                "to_number(dat.xml_data.extract('//E9432/text()').getStringVal()) Extent_West, " \
                "dat.xml_data.extract('//E10424/text()').getStringVal() product_type, " \
                "dat.xml_data.extract('//E9856/text()').getStringVal() product_id, " \
                "dat.xml_data.extract('//E9244/text()').getStringVal() record_language, " \
                "dat.xml_data.extract('//E9246/text()').getStringVal() record_characterSet, " \
                "dat.xml_data.extract('//E9262/text()').getStringVal() standard_name, " \
                "dat.xml_data.extract('//E9264/text()').getStringVal() standard_version, " \
                "usr.LOGIN user_name, " \
                "usr.description OWNER_DESC, " \
                "usr.email OWNER_EMAIL, " \
                "dat.sv_5 RECORD_TYPE " \
                "FROM metastar.bat_records_104 dat, " \
                "metastar.bat_users usr, " \
                "metastar.bat_states st " \
                "WHERE dat.state_uid IN (164,166,168,172) " \
                "AND usr.user_uid = dat.user_uid " \
                "AND st.state_uid = dat.state_uid "
#                /* state is Draft, Approve, Published or ZPublished */
    cur = con.cursor()

    data = cur.execute(edc_query)

    return data


def import_discovery_records(con):

    #Required for email validation
    from validate_email import validate_email


    #Get the list of available records
    pkg_list = get_record_list()

    #Get the number of discovery records have already been imported.
    record_count_filename = 'discovery_record_count.txt'
    if not os.path.exists(record_count_filename):
        previous_count = 0
    else :
        with open(record_count_filename, 'r') as record_count_file :
            previous_count = int(record_count_file.read())
    print previous_count

    index = 0
    records_created = 0

    (common_uids, common_titles) = load_common_records()


    #Create error file
    error_file = open('Discovery_errors.txt', 'a')

    #Get the raw records from discovery database
    data = execute_discovery_query(con)

    for result in data:

        try :

            edc_record = {}

            if index < previous_count :
                index += 1
                continue

            #Ignore records with null title
            if not result[0] :
                index += 1
                continue
            if result[14] and str(result[14]) in common_uids:
                index += 1
                continue

            #Ignore all the records available in ODSI
            if result[0] in common_titles:
                index += 1
                continue

            #---------------------------------------------------------------------<< Record state >>-----------------------------------------------------------------------
            state_convert_dict = {'Draft': 'DRAFT', 'Approve': 'PENDING PUBLISH', 'Published': 'PUBLISHED', 'ZPublished': 'ARCHIVED'}
            edc_record['edc_state'] = state_convert_dict[result[3]]

            # Ignore DRAFT records or Theme records (Records with Theme in title).
            if edc_record['edc_state'] == 'DRAFT' or '(Theme)' in result[0]:
                index += 1
                continue

            #---------------------------------------------------------------------<< Record Author >>----------------------------------------------------------------------
            username = result[46]
            user_id = get_user_id(username)
            if not user_id :
                username = admin_user
                user_id = get_user_id(admin_user)
#            print 'username, userid --------------------> ', username, user_id
            edc_record['author'] = user_id


            #---------------------------------------------------------------<< Dataset name and Title >>-------------------------------------------------------------------
            title = result[0].strip()

            #Remove (DEPRECATED) from the record title
            if title.startswith('(DEPRECATED) ') :
                title = title.replace('(DEPRECATED) ', '').strip()
                edc_record['notes'] = 'DEPRECATED - The resource(s) that this record refers is obsolete and may be scheduled for retirement. Please see the Replacement Record reference in the Data Currency / Update section.'
            else :
                edc_record['notes'] = result[1] or ' '

            edc_record['name'] = get_record_name(pkg_list, title);
            edc_record['title'] = title

            #--------------------------------------------------------------------<< Record Purpose >>-----------------------------------------------------------------------
            edc_record['purpose'] = result[4]

            #-------------------------------------------------------------------<< Record License ID >>---------------------------------------------------------------------
            if result[32] and result[32].lower() == 'yes':
                edc_record['license_id'] = "2"
            else:
                edc_record['license_id'] = "22"

            #----------------------------------------------------------------------<< Record type >>------------------------------------------------------------------------
            edc_record['type'] = 'Geographic'

            #-----------------------------------------------------<< Records Organization and Sub-organization >>-----------------------------------------------------------
            (org_title, sub_org_title) = get_organization(result[2])
            print org_title, sub_org_title
            edc_record['org'] = get_organization_id(org_title)
            edc_record['sub_org'] = get_organization_id(sub_org_title)
            edc_record['owner_org'] = edc_record['sub_org']

            #-------------------------------------------------------------------<< ISO topic category >>---------------------------------------------------------------------
            iso_topic_cat = (result[29] or 'unknown').split(',')
            edc_record['iso_topic_cat'] = iso_topic_cat

            #-------------------------------------------------------------------------<< Keywords >>-------------------------------------------------------------------------
            # Extract the keywords(tags) names and add the list of tags to the record.
            keywords = []
            if result[5] :
                keywords = result[5].split(',')


            edc_record['tags'] = [{'name' : remove_invalid_chars(keyword).strip()} for keyword in keywords if keyword and len(keyword) > 1]

            #----------------------------------------------------------------------<< Record Status >>-----------------------------------------------------------------------
            resource_status = result[6] or 'onGoing'
            edc_record['resource_status'] = resource_status

            #---------------------------------------------------------------------<< Record Contacts >>----------------------------------------------------------------------
            contact_names = []
            contact_emails = []
            contact_orgs = []
            if result[7]:
                contact_names = result[7].split(',')
            if result[8]:
                contact_emails = result[8].split(',')
            if result[9]:
                contact_orgs = result[9].split(',')

            #Validate emails
            contact_emails = [contact_email if (contact_email and validate_email(contact_email)) else 'databc@gov.bc.ca' for contact_email in contact_emails]

            contact_names = [contact_name if contact_name else 'DataBC Operations'  for contact_name in contact_names]
            # Adding dataset contacts
            contacts = []

            contact_len = min(len(contact_names), len(contact_emails), len(contact_orgs))

            for i in range(contact_len):
#                (contact_org, contact_sub_org) = get_organization(contact_orgs[i])
                contacts.append({'name': contact_names[i], 'email': contact_emails[i], 'delete': '0', 'organization': edc_record['org'], 'role' : 'pointOfContact', 'private' : 'Display'})

            edc_record['contacts'] = contacts

            #----------------------------------------------------------------------<< Record Constraints >>---------------------------------------------------------------
            # Set record view audience and download audience to public
            if (result[11] and result[11].lower() == 'yes'):
                edc_record['view_audience'] = 'Public'
            else :
                edc_record['view_audience'] = 'Government'

            if (result[12] and result[12].lower() == 'yes'):
                edc_record['download_audience'] = 'Public'
            else:
                edc_record['download_audience'] = 'Government'

            if (result[13] and result[13] == 'TRUE'):
                edc_record['privacy_impact_assessment'] = 'Yes'
            else :
                edc_record['privacy_impact_assessment'] = 'No'

            edc_record['metastar_uid'] = str(result[14])

            edc_record['lineage_statement'] = result[18]

            if result[19] and result[19].lower().startswith('tru'):
                edc_record['metadata_visibility'] = 'Public'
            else:
                edc_record['metadata_visibility'] = 'IDIR'

            edc_record['archive_retention_schedule'] = result[20]
            edc_record['retention_expiry_date'] = result[21]
            edc_record['source_data_path'] = result[22]

            #-----------------------------------------------------------<< Record security classification >>--------------------------------------------------------------
            security_class = result[28]

            security_dict = {'topSecret': 'MEDIUM-SENSITIVITY', 'secret': 'MEDIUM-SENSITIVITY', 'restricted' : 'MEDIUM-SENSITIVITY', 'confidential': 'MEDIUM-SENSITIVITY', 'unclassified' : 'LOW-PUBLIC'}

            if security_class and security_class in security_dict :
                edc_record['security_class'] = security_dict[security_class]
            else :
                edc_record['security_class'] = 'LOW-PUBLIC'


            #---------------------------------------------------------------------<< Record dates >>----------------------------------------------------------------------
            # Adding dataset dates
            dates = []
            if result[30] :
                dates.append({'type': 'Created', 'date': result[30], 'delete': '0'})
            if result[31] :
                dates.append({'type': 'Modified', 'date': result[31], 'delete': '0'})

            #Add the publish date for records with publish state.
            if edc_record['edc_state'] == 'Published' :
                edc_record['publish_date'] = str(datetime.date.today())

            edc_record['dates'] = dates

            #------------------------------------------------------------------<< Metadata Information >>-----------------------------------------------------------------
            metadata_language = result[42] or 'English'
            metadata_character_set = result[43] or 'utf8'
            metadata_standard_name = result[44]  or 'North American Profile of ISO 19115-1:2014 - Geographic information - Metadata (NAP-Metadata)'   #Add default value here if there is any
            metadata_standard_version = result[45]  or  'n/a' #Add default value here if there is any

            edc_record['metadata_language'] = metadata_language
            edc_record['metadata_character_set'] = metadata_character_set
            edc_record['metadata_standard_name'] = metadata_standard_name
            edc_record['metadata_standard_version'] = metadata_standard_version

            #---------------------------------------------------------------------<< Dataset Extent >>--------------------------------------------------------------------
            #Get dataset map extent coordinates
            if (result[36] and result[37] and result[38] and result[39]) :
                north = result[36]
                south = result[37]
                east = result[38]
                west = result[39]

                spatial_extent = {"type":"Polygon",
                               "coordinates":[[[west, south], [west, north], [east, north], [east, south],[west, south]]]
                               }
                edc_record['spatial'] = json.dumps(spatial_extent)

                edc_record['west_bound_longitude'] = west
                edc_record['east_bound_longitude'] = east
                edc_record['south_bound_latitude'] = south
                edc_record['north_bound_latitude'] = north


            resources = []

            resource_rec = {}

            #----------------------------------------------------------------<< Resource name and format >>---------------------------------------------------------------
            resource_rec['name'] = result[0]

            resource_rec['format'] = 'SHP'

            #---------------------------------------------------------------------<< Projection Name >>-------------------------------------------------------------------
            #Assigning projection name to the record
            #Projection code for all the records is EPSG:3005 - NAD83/BC ALBERS
            projection_name = 'EPSG_3005 - NAD83 BC Albers'
            resource_rec['projection_name'] = projection_name


            #-----------------------------------------------------------------------<< Resource type >>-------------------------------------------------------------------
            resource_type = result[23] or 'Data'
            resource_rec['edc_resource_type'] = resource_type.strip()


            #------------------------------------------------------------------<< Resource Update Cycle >>----------------------------------------------------------------
            # Set record's resource update cycle
            update_cycle = result[10] or 'unknown'
            resource_rec['resource_update_cycle'] = update_cycle

            #----------------------------------------------------------------<< Resource Storage Location >>--------------------------------------------------------------
            storage_location = result[24]

            is_bcgw_record = False
            if storage_location and 'LRDW' in storage_location :
                #storage_location = "BCGW Data Store"
                resource_rec['resource_storage_location'] = 'resource_storage_location'
                is_bcgw_record = True
            else :
                resource_rec['resource_storage_location'] = 'External'


            #--------------------------------------------------------------<< Resource Storage Access Method >>-----------------------------------------------------------
            access_method = 'Indirect Access'
            resource_rec['resource_storage_access_method'] = access_method

            #-------------------------------------------------------------------------<< Resource URL >>------------------------------------------------------------------
            #Create resource_url for record
            resource_url = ' '
            if is_bcgw_record :
                product_type_id_dic = {'Feature Type': '0', 'Theme' : '1', 'Packaged Product' : '2'}
                product_type = result[40]
                product_id = result[41]
                product_type_id = None
                if product_type and product_type in product_type_id_dic :
                    product_type_id = product_type_id_dic[product_type]
                if product_id and product_type_id:
                    resource_url = 'https://apps.gov.bc.ca/pub/dwds/addProductsFromExternalApplication.do?productTypeId={0}&productId={1}'.format(product_type_id, product_id)

            resource_rec['url'] = resource_url

            resource_rec['data_collection_start_date'] = result[16]
            resource_rec['data_collection_end_date'] = result[17]

            # Add the current resource record to the list of dataset resources
            resources.append(resource_rec)

            # Add the list of dataset resources to the dataset
            edc_record['resources'] = resources
            #media_cur.close()

#            pprint.pprint(edc_record)

            #Extract resource object name
            object_name = result[34]

            if object_name and (object_name.startswith('WHSE_') or object_name.startswith('REG_')) :
                edc_record['object_name'] = object_name



            #--------------------------------------------------------------------<< Dataset Features >>-------------------------------------------------------------------
            # Adding dataset features
            features = []
            if (result[25]):
                feature_class_names = result[25].split('|')
                feature_class_desciptions = []
                description_len = 0
                if (result[26]) :
                    feature_class_description_str = ''
                    if isinstance(result[26], str):
                        feature_class_description_str = result[26]
                    else :
                        feature_class_description_str = result[26].read()
                    feature_class_desciptions = feature_class_description_str.split('|')

                    description_len = len(feature_class_desciptions)

                for i in range(len(feature_class_names)):
                    feature_dict = {'name' : feature_class_names[i]}
                    if description_len > i :
                        feature_dict['description'] = feature_class_desciptions[i]
                    features.append(feature_dict)
            edc_record['feature_types'] = features

            #--------------------------------------------------------------------<< Dataset More info >>------------------------------------------------------------------
            more_info = []
            if (result[27]) :
                more_info_links_str = ''
                if isinstance(result[27], str):
                    more_info_links_str = result[27]
                else :
                    more_info_links_str = result[27].read()
                more_info_links = more_info_links_str.split('|')

                for i in range(len(more_info_links)):
                    more_info_link = more_info_links[i]
                    if is_valid_url(more_info_link) :
                        more_info.append({'link': more_info_link, 'delete': '0'})

            edc_record['more_info'] = more_info

#            pprint.pprint(edc_record)
            (record_info, errors) = edc_package_create(edc_record)

            if  record_info :
                pkg_list.append(edc_record['name'])
                records_created += 1
            else :
                pprint.pprint(errors)

                error_file.write('Error in importing record with UID : ' + str(result[14]) + '\n')
                error_file.write('Record info :\n')
                json.dump(edc_record, error_file)
                error_file.write('\nError details :')
                json.dump(errors, error_file)
                error_file.write('\n\n------------------------------------------------------------------------------------------------------------------------------------\n\n')
            index = index + 1
        except Exception, e:
            print str(e)
            error_file.write('Exception in importing record with UID ' + str(result[14])) + '\n'
            pass

    print "Total number of records : ", index
    print "Records created : ", records_created
    con.close()
    error_file.close()

    #Save the number of discovery records have been imported.
    with open('discovery_record_count.txt', 'w') as record_count_file :
        record_count_file.write(index)


def find_missing_orgs(con):
#    projection_names_file = open('Records_with_UTM_projection.txt', 'w')

    edc_query = "SELECT SUBSTR(dat.xml_data.extract('//E9254/text()').getStringVal(),1,300) Data_Custodian_organization " \
                "FROM metastar.bat_records_104 dat " \
                "WHERE dat.state_uid IN (164,166,168,172) "
#                /* state is Draft, Approve, Published or ZPublished */
    print 'Before query ...'
    cur = con.cursor()

    data = cur.execute(edc_query)
    #Get the raw records from discovery database

    org_error_file = open('orgs_not_available.txt', 'w')

    missing_orgs = []
    try :
        for result in data:
#         #Add the record uid for records with projection name value = UTM in discovery to a file.
#         if result[15] and result[15].strip() == 'UTM':
#             projection_names_file.write('%s\n' % str(result[14]))
#
#     projection_names_file.close()
#     pass
            (org_title, suborg_title) = get_organization(result[0])
            org_id = get_organization_id(org_title)
            suborg_id = get_organization_id(suborg_title)


            if (not org_id) or (not suborg_id) :
                if result[0] not in missing_orgs :
                    missing_orgs.append(result[0])
    except Exception, e :
        print str(e)
        pass

    for org in missing_orgs :
        org_error_file.write("%s \n" % (org))
    org_error_file.close()

def import_data():

    data_source = raw_input("Data source (ODC/Discovery): ")
    con =  get_connection(data_source)

    try:
        if data_source.lower() == 'odc' :
            import_odc_records(con)
        elif data_source.lower() == 'discovery' :
            import_discovery_records(con)
#            find_missing_orgs(con)
        else :
            print "No data source is given."
    except:
        pass

import_data()