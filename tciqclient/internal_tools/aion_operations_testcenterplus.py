import argparse
import time
from utils.Temeva import Temeva
from powerapp import configuration
from pprint import pprint

# determine version and its version id to be used
def determine_target_version(all_products, target_product, prod_ver):
    print('=== Determine target version to be used')
    for product in all_products:
        if product['name'] == target_product:
            # list all available versions for target product
            if prod_ver == 'latest':
                print('Latest {} image secified to be used'.format(target_product))
                print('Determining latest version...')
                target_ver = product['version_summaries'][0]['version']
                target_ver_id = product['version_summaries'][0]['id']
                print('Latest version of {} product detected: {}'.format(target_product, target_ver))
                print('Corresponding product version id: ' + target_ver_id)
            else:
                target_ver = prod_ver
                print('{} image version secified to be used: {}'.\
                        format(target_product, product_version))
                print('Getting version id...')
                target_ver_id = False
                for version in product['version_summaries']:
                    if version['version'] == target_ver:
                        target_ver_id = version['id']
                        print('Target product version id found: ' + target_ver_id)
                if not target_ver_id:
                    print('ERROR! Target version: {} for product {} not found!'\
                          .format(target_ver, target_product))

    return target_ver, target_ver_id

# determine if target version is downloaded in the Cluster 
def determine_ver_available(target_product, target_ver):
    print('=== Check if target version is downloaded in the Cluster')
    # list all products
    products = temeva.list_products()

    downloaded_version_list = []
    for product in products:
        if product['name'] == target_product:
            # list all available versions for target product
            print('All available {} versions are: '.format(target_product))
            versions = product['version_summaries']
            for ver in versions:
                downloaded_version_list.append(ver['version'])
                if ver['deployed']:
                    print("Version: " + ver['version'] + ". deployed: True")
                else:
                    print("Version: " + ver['version'] + ". deployed: False")

    if target_ver in downloaded_version_list:
        print('Target {} version {} is already downloaded.'\
              .format(target_product, target_ver))
        ver_exist = True
    else:
        print('Target {} version {} is NOT found.'\
              .format(target_product, target_ver))
        print('Available {} versions are: {}'\
              .format(target_product, downloaded_version_list))
        ver_exist = False

    return ver_exist

def delete_all_unused_images(temeva):
    print('=== Delete all downloaded product images that are not in use')
    # list all products
    print('--- Inventory Before Deletion')
    products = temeva.list_products()
    for product in products:
        print('Product - {} inventory:'.format(product['name']))
        versions = product['version_summaries']
        for ver in versions:
            if ver['deployed']:
                print("\tVersion: " + ver['version'] + ". deployed: True")
            else:
                print("\tVersion: " + ver['version'] + ". deployed: False. Delete!")
                temeva.delete_product_version(ver_id=ver['id'])

    print('--- Inventory After Deletion')
    products = temeva.list_products()
    for product in products:
        print('Product - {} inventory:'.format(product['name']))
        versions = product['version_summaries']
        for ver in versions:
            if ver['deployed']:
                print("\tVersion: " + ver['version'] + ". deployed: True")
            else:
                print("\tVersion: " + ver['version'] + ". deployed: False")

# download target product version on Cluster
def download_target_ver(target_ver, target_ver_id):
    print('=== Download target version: ' + target_ver)
    resp = temeva.product_version_download(version_id=target_ver_id)
    start_time = time.time()
    print('version:{} download status: {}'.format(target_ver, resp['progress']['status']))
    print('version:{} download progress: {}'.format(target_ver, resp['progress']['percent']))
    cnt = 0
    # pulling product status to make sure target version is downloaded
    # set timeout to 60x5=300s
    download_success = False
    while cnt < 60 and not download_success:
        products = temeva.list_products()
        for product in products:
            if product['name'] == target_product:
                versions = product['version_summaries']
                for ver in versions:
                    if ver['version'] == target_ver:
                        print('Target version:{} found!'.format(target_ver))
                        download_success = True
                        end_time = time.time()
                        print("Product version download time: " + str(end_time - start_time) + " s")
                        break
                    else:
                        print('Pulling product version, and wait 5 seconds...')
                        time.sleep(5)
                        cnt += 1

    if not download_success:
        end_download = time.time()
        print('WARNING! Target version is NOT downloaded after ' + \
              str(end_download - start_download) + " s")
        
    return download_success

# deploy target product instance with target version
def deploy_prod_instance(target_product, product_version,location_name):
    print('=== Deploy target product instance with target version')
    # list all products and its versions from connected platform(temeva.com or oriontest.net)
    all_products = temeva.cluster_list_products()
    target_ver, target_ver_id = determine_target_version(all_products, target_product, product_version)
    if target_ver_id:
        target_ver_exist = determine_ver_available(target_product, target_ver)
        if not target_ver_exist:
            target_ver_exist = download_target_ver(target_ver, target_ver_id)
        
        if target_ver_exist:
            # deploy a product instance    
            print('Deploy a {} instance with version: {}'.format(target_product, target_ver))
            create_prod_inst = temeva.create_product_inst(version_id=target_ver_id,location=location_name)
            #print(create_prod_inst)
            start_time = time.time()
            prod_inst_id = create_prod_inst['id']
            print('Deployed TestCenterPlus instance id: ' + prod_inst_id)
            # pull product instance status
            print('Check deployed TestCenterPlus instance status:')
            prod_inst = temeva.get_product_instance(inst_id=prod_inst_id)
            print_instance_status(prod_inst)
            # pull instance state until instance state is running
            cnt = 0
            while prod_inst['state'] != 'running' or \
                  prod_inst['health']['status'] != 'healthy' and \
                  cnt < 60:
                print('Instance is not in \"running\" and \"healthy\" state, wait 5 seconds and '
                      'pulling status...')
                prod_inst = temeva.get_product_instance(inst_id=prod_inst_id)
                cnt += 1
                time.sleep(5)


            end_time = time.time()
            time_taken = str(end_time - start_time)
            if cnt == 60:
                print('ERROR! {} product instance is not ready in {} seconds'.format(time_taken))
                target_url = ""
            else:
                print('Instance READY!')
                print('Total time taken to deploy an instance: {} seconds'.format(time_taken))
                print('Check instance status:')
                print_instance_status(prod_inst)
                print("========================")
                print(prod_inst)
                target_url = get_inst_url(prod_inst)
                print('URL of deployed instance: ' + target_url)
        else:
            print('Target {} product version:{} not downloaded, can not deploy instance'\
                  .format(target_product, product_version))
            return False, False, False

        return prod_inst_id, target_url, target_ver

    else:
        return False, False, False

# given a product instance, print its status
def print_instance_status(prod_inst):
    print('\t- health status: ' + prod_inst['health']['status'])
    print('\t- health score: ' + str(prod_inst['health']['score']))
    print('\t- instance state: ' + prod_inst['state'])
    print('\t- progress status: ' + prod_inst['progress']['status'])
    print('\t- progress percent: ' + str(prod_inst['progress']['percent']))

# given a product instance, return its url address
def get_inst_url(inst):
    for port in inst['ports']:
        #if port['name'] == 'web-application':
        if port['name'] == 'testcenterplus':
            url = port['http']['url']
            target_url = url.split('/')[-1]

    return target_url

# get and print all product instances
def get_prod_insts(temeva, target_product):
    print('===List all {} product instances on Cluster'.format(target_product))
    prod_insts = temeva.list_product_instances()
    print(prod_insts)
    prod_inst_id_list = []
       
    if target_product == 'all':
        always = True
    else:
        always = False

    for inst in prod_insts:
        product = inst['product']['name']
        if product == target_product or always:
            loc_name = inst['location']['name']
            prod_ver = inst['product_version']['version']
            inst_id = inst['id']
            url = get_inst_url(inst)
            print('Location: {}, ver: {}, instance id: {}, url: {}, {}'\
                  .format(loc_name, prod_ver, inst_id, url, product))
            print('Location: {}, ver: {}, instance id: {},  {}'\
                  .format(loc_name, prod_ver, inst_id, product))
            prod_inst_id_list.append(inst['id'])

    if len(prod_inst_id_list) == 0:
        print('WARNING! No product instance found for product: ' + target_product)

    return prod_inst_id_list


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tests the execution of a '
                                     'testcase')
    """ platform info """
    parser.add_argument('--subdomain', help='Temeva subdomain',
                        default='spirent')
    parser.add_argument('-u', '--email', help='Temeva email',
                        default='testcenterplus_testing@spirent.com')
    parser.add_argument('-p', '--password', help='Temeva password',
                        default='TestCenter+')
    parser.add_argument('--temeva_url', help='URL of Temeva backend. In order'
                        ' to insert the subdomain automatically, you can '
                        'specify the url as follows: https://{}.temeva.com',
                        default='http://10.109.124.244')
    parser.add_argument('-prod', '--product', help='product name',
                        default='TestCenter+')
    parser.add_argument('-prod_ver', '--product_version', 
                        help='product version to be downloaded. If specify latest,'
                        ' script will get the latest version available',
                        default='latest')
    parser.add_argument('-d', '--deploy', 
                        help='Specify to deploy a new product instance',
                        action='store_true')
    parser.add_argument('--cleanup_images', 
                        help='Specify to delete all not in use product images '
                        'downloaded on Cluster',
                        action='store_true')
    parser.add_argument('--list_inventory', 
                        help='Specify to list all product instances',
                        action='store_true')
    parser.add_argument('-del_prod_insts', '--delete_all_product_instances',
                        help='all or product name. If specify \"all\", it will delete'
                        ' ALL instances from inventory. If specify any product name, '
                        'ex: Trafficapp_client, it will delete all Trafficapp_client app instances',
                        default='')
    parser.add_argument('-del_inst', 
                        help='delete instance by specified instance id',
                        action='store_true')

                        
    args = parser.parse_args()
    if '{}' in args.temeva_url:
        args.temeva_url = args.temeva_url.format(args.subdomain)
    temeva = Temeva(args.email, args.password, args.subdomain,
                    base_url=args.temeva_url)
    configuration.host = '{}/api'.format(args.temeva_url)
    configuration.access_token = temeva.access_token()
    configuration.refresh_token = temeva.refresh_token()
    target_product = args.product
    product_version = args.product_version
    cleanup_images = args.cleanup_images
    list_inventory = args.list_inventory
    print(args.delete_all_product_instances)
    delete_prod_insts = args.delete_all_product_instances
    delete_inst_id = args.del_inst
    deploy = args.deploy
    

    if cleanup_images:
       delete_all_unused_images(temeva)

    if deploy:
        location ='WebApp-Compliance-Scan'
        prod_inst_id, target_url, prod_ver = deploy_prod_instance(target_product, \
                                                                product_version,location)
        if prod_inst_id:
            # write params to a file so jenkins can pass along the params
            file_path = './deployed_instance_info.txt'
            f = open(file_path, 'w+')
            f.write('INSTANCE_ID=' + prod_inst_id)
            f.write('\nTestCenter_Plus_IP=' + target_url)
            f.write('\nTestCenterPlus_VERSION=' + prod_ver)
            f.write('\nACCESS_TOKEN=' + configuration.access_token)
            f.write('\nREFRESH_TOKEN=' + configuration.refresh_token + '\n')
            f.close()
        

    if list_inventory:
        print("Inside")
        # check current product instance inventory
        prod_inst_id_list = get_prod_insts(temeva, 'all')

    if delete_prod_insts:
        print('delete product: {} instances'.format(delete_prod_insts))
        prod_inst_id_list = get_prod_insts(temeva, target_product)
        for inst_id in prod_inst_id_list:
            print('delete product instance id: ' + inst_id)
            temeva.delete_product_instance(inst_id=inst_id)
            time.sleep(30)

    # delete app instance by its instance id
    if delete_inst_id:
        location ='WebApp-Compliance-Scan'
        prod_insts = temeva.list_product_instances()
        for inst in prod_insts:
            product = inst['product']['name']
            loc_name = inst['location']['name']

            if product == target_product and loc_name==location:
                inst_id = inst['id']
                print(inst_id)
                print('delete product instance id: ' + inst_id)
                temeva.delete_product_instance(inst_id=inst_id)
        else:
            print("No Instance with "+location+ " is found")