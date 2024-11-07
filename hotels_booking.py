import tkinter as tk
from tkinter import messagebox
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from geopy.distance import geodesic

def extract_hotels(driver):
    hotels_list = []
    previous_count = 0
    current_count = 0
    max_scroll_attempts = 5
    scroll_attempts = 0

    while scroll_attempts < max_scroll_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        hotels = driver.find_elements("xpath", '//div[@data-testid="property-card"]')
        current_count = len(hotels)
        print(f'Nombre d\'hôtels chargés : {current_count}.')

        if current_count > previous_count:
            previous_count = current_count
            scroll_attempts = 0
        else:
            scroll_attempts += 1

        if scroll_attempts >= max_scroll_attempts:
            break

    for hotel in hotels:
        hotel_dict = {}
        try:
            hotel_dict['hotel'] = hotel.find_element("xpath", './/div[@data-testid="title"]').text
        except Exception:
            hotel_dict['hotel'] = 'N/A'

        try:
            stars_count = len(hotel.find_elements("xpath", './/div[@data-testid="rating-stars"]/span'))
            hotel_dict['Étoiles'] = stars_count
        except Exception:
            hotel_dict['Étoiles'] = 'N/A'

        try:
            price_text = hotel.find_element("xpath", './/span[@data-testid="price-and-discounted-price"]').text
            price_value = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
            hotel_dict['Prix'] = float(price_value) if price_value else 'N/A'
        except Exception:
            hotel_dict['Prix'] = 'N/A'

        try:
            note_text = hotel.find_element("xpath", './/div[@data-testid="review-score"]/div[1]').text.strip()
            hotel_dict['Note /10'] = float(note_text.split()[-1].replace(',', '.'))
        except Exception:
            hotel_dict['Note /10'] = 'N/A'

        # Extraire le lien de l'hôtel
        try:
            hotel_link = hotel.find_element("xpath", './/a[@data-testid="title-link"]').get_attribute('href')
            hotel_dict['Lien'] = hotel_link if hotel_link else 'N/A'
        except Exception:
            hotel_dict['Lien'] = 'N/A'

        hotels_list.append(hotel_dict)

    return hotels_list

def fetch_details(driver, hotel_link):
    driver.get(hotel_link)
    time.sleep(5)
    
    # Récupérer la latitude et la longitude
    try:
        latlng = driver.find_element("xpath", './/a[@data-atlas-latlng]').get_attribute("data-atlas-latlng")
        if latlng:
            latitude, longitude = map(float, latlng.split(','))
        else:
            latitude, longitude = None, None
    except Exception:
        latitude, longitude = None, None

    # Récupérer l'adresse de l'hôtel
    try:
        address_element = driver.find_element("xpath", '//span[contains(@class, "hp_address_subtitle")]')
        address = address_element.get_attribute("textContent").strip()  # Récupérer le texte pur de l'adresse
    except Exception:
        address = 'Adresse non disponible'
    
    return latitude, longitude, address

def calculate_distance(hotel_coords, event_coords):
    try:
        distance_km = geodesic(hotel_coords, event_coords).kilometers
        return round(distance_km, 2)
    except Exception as e:
        print(f"Erreur lors du calcul de la distance : {e}")
        return 'Erreur de calcul'

def run_scraping(destination, checkin_date, checkout_date):
    event_coords = (36.74196135173365, 15.11610252956532)  # Coordonnées de l'événement
    page_url = f'https://www.booking.com/searchresults.fr.html?ss={destination}&checkin={checkin_date}&checkout={checkout_date}&group_adults=2&no_rooms=1&group_children=0&nflt=ht_id%3D204'

    options = webdriver.ChromeOptions()
    service = ChromeService(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(page_url)
    time.sleep(5)

    hotels_list = extract_hotels(driver)

    for hotel in hotels_list:
        hotel_link = hotel.get('Lien')
        if hotel_link and hotel_link != 'N/A':
            hotel_coords = fetch_details(driver, hotel_link)
            latitude, longitude, address = hotel_coords
            
            if all(coord is not None for coord in (latitude, longitude)):  # Vérifiez si les coordonnées sont valides
                distance = calculate_distance((latitude, longitude), event_coords)
                hotel['Latitude'] = latitude
                hotel['Longitude'] = longitude
                hotel['Adresse'] = address
                hotel['Distance de l\'événement en Km'] = distance
            else:
                hotel['Distance de l\'événement en Km'] = 'Coordonnées non disponibles'
                hotel['Latitude'] = 'N/A'
                hotel['Longitude'] = 'N/A'
                hotel['Adresse'] = address
        else:
            hotel['Distance de l\'événement en Km'] = 'N/A'
            hotel['Latitude'] = 'N/A'
            hotel['Longitude'] = 'N/A'
            hotel['Adresse'] = 'N/A'

    df = pd.DataFrame(hotels_list)
    file_name = f'Hotels - {destination} - {checkin_date} - {checkout_date}.xlsx'
    df.to_excel(file_name, index=False)

    driver.quit()

    return len(hotels_list), file_name

def on_submit():
    destination = entry_destination.get()
    checkin_date = entry_checkin.get()
    checkout_date = entry_checkout.get()

    if not destination or not checkin_date or not checkout_date:
        messagebox.showerror("Erreur", "Veuillez remplir tous les champs.")
        return

    try:
        num_hotels, file_name = run_scraping(destination, checkin_date, checkout_date)
        messagebox.showinfo("Résultat", f'Nombre total d\'hôtels récupérés : {num_hotels}.\nLes résultats ont été enregistrés sous : {file_name}.')
    except Exception as e:
        messagebox.showerror("Erreur", str(e))

# Configuration de l'interface graphique
root = tk.Tk()
root.title("Scraping d'Hôtels")

tk.Label(root, text="Destination :").pack(pady=5)
entry_destination = tk.Entry(root)
entry_destination.pack(pady=5)

tk.Label(root, text="Date d'arrivée (YYYY-MM-DD) :").pack(pady=5)
entry_checkin = tk.Entry(root)
entry_checkin.pack(pady=5)

tk.Label(root, text="Date de départ (YYYY-MM-DD) :").pack(pady=5)
entry_checkout = tk.Entry(root)
entry_checkout.pack(pady=5)

submit_button = tk.Button(root, text="Lancer le Scraping", command=on_submit)
submit_button.pack(pady=20)

root.mainloop()
