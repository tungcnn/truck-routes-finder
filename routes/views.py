import csv
import json
import requests
import os
from dotenv import load_dotenv
from django.http import HttpResponse
from .models import FuelStop

load_dotenv()

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTES_FIELDMASK = "routes.distanceMeters,routes.legs.distanceMeters,routes.legs.steps.distanceMeters,routes.legs.steps.startLocation,routes.legs.steps.endLocation,routes.legs.steps.navigationInstruction"
ROUTES_HEADERS = {
    'X-Goog-Api-Key':os.getenv('GOOGLE_MAP_API_KEY'),
    'Content-Type':'application/json',
    'X-Goog-FieldMask':ROUTES_FIELDMASK
    }

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
NEARBY_FIELDMASK = "places.id,places.location,places.fuelOptions.fuelPrices.type,places.fuelOptions.fuelPrices.price.units"
NEARBY_HEADERS = {
    'X-Goog-Api-Key':os.getenv('GOOGLE_MAP_API_KEY'),
    'Content-Type':'application/json',
    'X-Goog-FieldMask':NEARBY_FIELDMASK
    }

DISTANCE_LIMT = 500 * 1609.34
DEFAULT_FUEL_PRICE = {
    "fuelPrices": [
        {
            "type": "DIESEL",
            "price": {
              "units": 3.5,
            }
        }]}

# Create your views here.
def importTruckStop(request):
    with open('fuel-prices-for-be-assessment.csv', newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(reader)

        if (not FuelStop.objects.exists()):  
            for row in reader:
                addressFull = ""
                googlePlaceId = ""
                
                for a in row[2:-4]:
                    addressFull += a
    
                url = f"https://maps.googleapis.com/maps/api/geocode/json?address={addressFull}&&key={os.getenv('GOOGLE_MAP_API_KEY')}"
    
                response = requests.get(url).json()
                
                if (response['status'] == "OK"):
                    googlePlaceId = response['results'][0]['place_id']

                FuelStop.objects.create(
                    truckStopId=row[0],
                    name=row[1],
                    address=addressFull,
                    city=row[-4],
                    state=row[-3],
                    rackId=row[-2],
                    retailPrice=row[-1],
                    googleMapId=googlePlaceId
                )
    return HttpResponse("Imported all truck")

def search(request):  
    routeRequest = json.dumps({
        "origin": {
            "address": request.GET.get('origin')
        },
        "destination" : {
            "address": request.GET.get('destination')
        },
        "units": "IMPERIAL"
    })
    
    response = requests.post(ROUTES_URL, data=routeRequest, headers=ROUTES_HEADERS)
    data = response.json()
    fuelStops= []
    
    if (data['routes'][0]['distanceMeters'] > DISTANCE_LIMT): 
        steps = data['routes'][0]['legs'][0]['steps']
        fuelStops = __getFuelStops(steps)
        
    intermediates = [{"placeId": fuelStop["id"]} for fuelStop in fuelStops]
    
    routeWithFuelStopsRequest = json.dumps({
        "origin": {
            "address": request.GET.get('origin')
        },
        "destination" : {
            "address": request.GET.get('destination')
        },
        "intermediates": intermediates,
        "units": "IMPERIAL"
    })
    
    response = requests.post(ROUTES_URL, data=routeWithFuelStopsRequest, headers=ROUTES_HEADERS).json()
    
    return __formatResponse(response['routes'][0]['legs'], fuelStops)
   
def __getFuelStops(steps):
    result = []
    distance_covered = 0
    
    for step in steps:
        step_distance = step['distanceMeters']
        distance_covered += step_distance

        if distance_covered >= DISTANCE_LIMT:
            stop_location = step['startLocation']
            nearbyRequest = json.dumps({
                "includedTypes": ["truck_stop"],
                "maxResultCount": 5,
                "rankPreference":"DISTANCE",
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": stop_location['latLng']['latitude'],
                            "longitude": stop_location['latLng']['longitude']
                        },
                        "radius": 20000.0
                    }
                }
            })
            
            response = requests.post(NEARBY_URL, data=nearbyRequest, headers=NEARBY_HEADERS)

            if (response.status_code == requests.codes.ok):
                fuelStops = response.json()['places']
                         
                for fuelStop in fuelStops:
                    if fuelStop.get('fuelOptions') == None: fuelStop['fuelOptions'] = DEFAULT_FUEL_PRICE
                    
                    fuelStop['fuelOptions']['fuelPrices'] = [price for price in fuelStop['fuelOptions']['fuelPrices'] if price['type'] == 'DIESEL']             
                    
                    fuelStopInDB = FuelStop.objects.filter(googleMapId=fuelStop['id'])
                    if (fuelStopInDB.exists()): fuelStop['fuelOptions']['fuelPrices'][0]['price']['units'] = fuelStopInDB[0].retailPrice                   
                
                fuelStops.sort(key=lambda fuelStop: int(fuelStop['fuelOptions']['fuelPrices'][0]['price']['units']))    
                result.append(fuelStops[0])                 
            
            distance_covered = 0
            
    return result

def __formatResponse(legs, fuelStops):
    totalPrice = 0
    i = 0
    
    for leg in legs[:-1]:
        totalPrice += (leg['distanceMeters'] / (1609.34*10))*float(fuelStops[i]['fuelOptions']['fuelPrices'][0]['price']['units'])
        i+=1
    
    response = {
        "totalPrice":round(totalPrice, 2),
        "legs":legs
    }
    
    return HttpResponse(json.dumps(response))