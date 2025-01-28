import requests

url = "http://52.137.123.13:3333"

class API: 
    def get_id(plate):
        return requests.get(f"{url}/get_id", json={"plate": plate}).json()["data"]

    def get_events(id):
        combined = requests.get(f"{url}/get_events", json={"id": id}).json()["data"]
        merged_list = []
        for item in combined:
            if item not in merged_list:
                merged_list.append(item)
        return merged_list

    def get_matches(id, season, event):
        return requests.get(f"{url}/get_matches", json={"event": event, "id": id, "season": season}).json()["data"]
    
    def get_seasons():
        return requests.get(f"{url}/get_seasons").json()["data"]