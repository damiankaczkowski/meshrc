import json
import requests
import time

class PromNetJson():
    def __init__(self):
        print("init")
        self.init_config()
        self.init_netjsongraph()

    def init_config(self):
        self.BMX_VERSION = "7"
        self.FILES_PATH = "./qmp"
        self.LABEL = "Prometheus 2 NetJson"
        self.PROTOCOL = "bmx" + self.BMX_VERSION
        self.VERSION = "0.1"
        self.METRIC = "rxRate"
        self.PROMETHEUS_HOST = "http://localhost:9090"

    def timer_start(self):
        self.time_start = time.time()

    def timer_end(self, task):
        print("{} in {:.3f}ms".format(task, (time.time() - self.time_start) * 1000) )

    def init_netjsongraph(self):
        self.njg = {}
        self.njg["type"] = "NetworkGraph"
        self.njg["label"] = self.LABEL
        self.njg["protocol"] = self.PROTOCOL
        self.njg["version"] = self.VERSION
        self.njg["metric"] = self.METRIC
        self.njg_nodes = {}
        self.njg_links = {}

    def merge_links(self, links):
        self.timer_start()
        online_links = set()
        for link in links:
            # sort to save bidirectional links only once
            n1, n2 = sorted([link["source"], link["target"]])
            online_links.add(n1)

            if not n1 in self.njg_links:
                self.njg_links[n1] = {}

            if not n2 in self.njg_links[n1]:
                self.njg_links[n1][n2] = {}

            self.njg_links[n1][n2]["source"] = n1
            self.njg_links[n1][n2]["target"] = n2

            if not "properties" in self.njg_links[n1][n2]:
                self.njg_links[n1][n2]["properties"] = {}

            if not "devs" in self.njg_links[n1][n2]["properties"]:
                self.njg_links[n1][n2]["properties"]["devs"] = {}
            self.njg_links[n1][n2]["properties"]["devs"][link["dev"]] = link["rxRate"]

        self.timer_end("merged links")
        self.timer_start()

        njg_links_set = set(self.njg_links.keys())
        for offline_link in (njg_links_set - online_links):
            del self.njg_links[offline_link]

        self.timer_end("removed offline links")

    def get_nodes_prometheus(self):
        self.timer_start()
        request_url = "{}/api/v1/query?query=bmx7_status".format(
                self.PROMETHEUS_HOST)
        response = requests.get(request_url).json()
        if response["status"] == "success":
            for node in response["data"]["result"]:
                node = node["metric"]
                self.njg_nodes[node["name"]] = {}
                self.njg_nodes[node["name"]]["id"] = node["id"]
                self.njg_nodes[node["name"]]["label"] = node["name"]
                self.njg_nodes[node["name"]]["properties"] = {}
                self.njg_nodes[node["name"]]["properties"]["address"] = node["address"]
                self.njg_nodes[node["name"]]["properties"]["revision"] = node["revision"]

        self.timer_end("get nodes prometheus")

        self.get_nodes_prometheus_details()
        print(self.njg_nodes)        
        return self.njg_nodes

    def api_call(self, query):
        return requests.get("{}/api/v1/query?query={}".format(self.PROMETHEUS_HOST, query)).json()["data"]["result"]

    def get_nodes_prometheus_details(self):
        for v in self.api_call("sum(node_network_receive_bytes{device=~'wlan.*mesh'}) by (instance)"):
            instance = v["metric"]["instance"]
            if instance in self.njg_nodes:
                self.njg_nodes[instance]["properties"]["traffic_mesh"] = v["value"][1]

        for v in self.api_call("sum(node_network_receive_bytes{device=~'wlan.*ap.*'}) by (instance)"):
            instance = v["metric"]["instance"]
            if instance in self.njg_nodes:
                self.njg_nodes[instance]["properties"]["traffic_ap"] = v["value"][1]

        for v in self.api_call("node_time - node_boot_time"):
            instance = v["metric"]["instance"]
            if instance in self.njg_nodes:
                self.njg_nodes[instance]["properties"]["uptime"] = self.hms_string(v["value"][1])

        for v in self.api_call("node_load15"):
            instance = v["metric"]["instance"]
            if instance in self.njg_nodes:
                self.njg_nodes[instance]["properties"]["load"] = v["value"][1]

        for v in self.api_call("node_memory_MemFree"):
            instance = v["metric"]["instance"]
            if instance in self.njg_nodes:
                self.njg_nodes[instance]["properties"]["memory"] = v["value"][1]

    def hms_string(self, sec_elapsed):
        h = int(int(sec_elapsed) / (60 * 60))
        m = int((int(sec_elapsed) % (60 * 60)) / 60)
        s = int(sec_elapsed) % 60
        return "{}:{:>02}:{:>02}".format(h, m, s)

    def get_links_prometheus(self):
        self.timer_start()
        request_url = "{}/api/v1/query?query=bmx7_link_rxRate".format(
                self.PROMETHEUS_HOST)
        response = requests.get(request_url).json()
        links = [] 
        if response["status"] == "success":
            for link in response["data"]["result"]:
                metric = link["metric"]
                value = link["value"][1]
                metric["rxRate"] = value
                links.append(metric)

        self.timer_end("get links prometheus")
        self.merge_links(links)

    def write_json(self, dest="netjson.json"):
        with open(dest, "w") as netjson_dest:
            netjson_dest.write(json.dumps(self.njg_out))

    def print_json(self):
        print(json.dumps(self.njg_out, indent="  "))

    def dump_json(self):
        self.timer_start()

        self.njg_out = self.njg

        self.njg_out["nodes"] = []
        for node in self.njg_nodes.values():
            self.njg_out["nodes"].append(node)

        self.njg_out["links"] = []
        for source in self.njg_links:
            for target in self.njg_links[source]:
                self.njg_out["links"].append(self.njg_links[source][target])

        self.timer_end("dump json")
        return self.njg_out

    def get_prometheus(self):
        self.get_nodes_prometheus()
        self.get_links_prometheus()
        return self.dump_json()

if __name__ == '__main__':
    s = PromNetJson()
    s.get_nodes_prometheus()
    s.get_links_prometheus()
    s.dump_json()
    s.print_json()