from kubernetes import client, config, watch
import re
import datetime
import time
import requests
import os
import argparse
import logging
 
# initialize the log settings
logging.basicConfig(filename='app.log',level=logging.INFO)
 
# Create the parser and add arguments
parser = argparse.ArgumentParser()
parser.add_argument("--deployment", help="give the deployment name that will be autoscaled",required=True)
parser.add_argument("--prometheus", help="promethues-server address", default="http://localhost:32300")
parser.add_argument("--namespace", help="deployment namepsace",required=True)
parser.add_argument("--memory_limit", help="Mention the memory limit mentioned in deployment resource defination",type=int,default=60, required=True)
parser.add_argument("--min-replicas", help="minimum replicas to maintain", type=int,default=1)
parser.add_argument("--max-replicas", help="maximum replicas to maintain",type=int,default=3)
parser.add_argument("--threshold", help="percentage threshold to trigger autoscaling",type=int,default=50)
args = parser.parse_args()


apps_v1 = client.AppsV1Api()
config.load_kube_config()
v1 = client.CoreV1Api()
signaling_pod=[]
pod_mem=[]
deployment_name=args.deployment
MEMORY_THRESHOLD=args.memory_limit
NAMESPACE=args.namespace
PROMETHEUS = args.prometheus
min_replicas =args.min_replicas
max_replicas=args.max_replicas
threshold=args.threshold
def pod_list():
    pod_list = v1.list_namespaced_pod(NAMESPACE)
    for pod in pod_list.items:
        #print("%s" % (pod.metadata.name))
        if pod.metadata.name.find(deployment_name) != -1:
            items=re.findall(rf"\b(?=\w)^.*{deployment_name}.*$\b(?!\w)",pod.metadata.name,re.MULTILINE)
            signaling_pod.append(items[0])
            logging.info("pod list"+'' + items[0])
def prometheus_data_fetch():
    for sigpod in signaling_pod:
        singnaling_pod_query="sum(container_memory_usage_bytes{pod='%s'}/1e+6)"%(sigpod)
        #print singnaling_pod_query
        end_of_month = datetime.datetime.today().replace(day=1).date()
        last_day = end_of_month - datetime.timedelta(days=1)
        duration = '[' + str(last_day.day) + 'd]'
        query={'query': singnaling_pod_query}
        response =requests.get(PROMETHEUS + '/api/v1/query', params=query)
        results = response.json()['data']['result']
        #print('{:%B %Y}:'.format(last_day))
        for result in results:
            #print('{value[1]}'.format(**result))
            pod_mem.append('{value[1]}'.format(**result))
            #average_pod_mem=(sum(map(float,pod_mem))/len(signaling_pod))


def autoscaler():
    try:
        pod_list()
        prometheus_data_fetch()
        try:
            if len(signaling_pod)==0:
                logging.error('Error occurred no pods found with name'+''+deployment_name)
            else:
                percentage_pod_mem=(sum(map(float,pod_mem))/(len(signaling_pod)*MEMORY_THRESHOLD)*100)
                logging.info("percentage of pods "+'' + deployment_name +''+ "is %d" %(percentage_pod_mem) )
                if percentage_pod_mem > threshold :
                    if len(signaling_pod)== max_replicas:
                        logging.info("Max replicas reached")
                    else:    
                        os.system("kubectl scale deployment {0} --replicas {1} -n {2}".format(deployment_name ,len(signaling_pod)+1, NAMESPACE) )
                elif percentage_pod_mem < threshold and len(signaling_pod)> min_replicas:
                    os.system("kubectl scale deployment {0} --replicas {1} -n {2}".format(deployment_name ,len(signaling_pod)-1, NAMESPACE) )
                else:
                    logging.info("memory usage fine")
        except Exception as e:
            logging.exception(str(e))
    except Exception as e:
        logging.exception(str(e))

if __name__ == "__main__":
    autoscaler()
