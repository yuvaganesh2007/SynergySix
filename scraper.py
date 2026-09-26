import time
import pandas as pd
from bs4 import BeautifulSoup
from seleniumbase import SB

cities=["HYD", "BLR", "BOM", "DEL"]
number=0
for row in cities:
    for col in cities:
        if(row is not col):

            url = f"https://flight.yatra.com/air-search-ui/dom2/trigger?ADT=1&CHD=0&INF=0&class=Economy&destination={row}&destinationCountry=IN&flight_depart_date=27%2F09%2F2026&hb=0&noOfSegments=1&origin={col}&originCountry=IN&type=O&unique=1248865360733&viewName=normal"

            # We run with headed mode (headless=False) so Akamai can see a real window size
            with SB(uc=True, headless=False, test=False) as sb:
                print("Step 1: Establishing genuine cookies on the homepage...")
                sb.uc_open_with_reconnect(url, 5)
                sb.sleep(4)
                
                # Simulate an initial human scroll to trigger Akamai's tracking
                sb.execute_script("window.scrollTo(0, 400);")
                sb.sleep(2)
                
                print("Step 2: Navigating to the journey-specific page using the active session...")
                sb.uc_open_with_reconnect(url, 3)
                
                print("Step 3: Attempting to bypass the Akamai challenge loop...")
                sb.uc_gui_handle_captcha()
                
                print("Waiting for flight listings to initially populate...")
                sb.sleep(10)
                
                # --- Check for Akamai Block ---
                dom_html = sb.get_page_source()
                if "sec-if-cpt-container" in dom_html and "flight-det" not in dom_html:
                    print("❌ Still blocked by Akamai.")
                    print("Please solve any checkbox on screen manually in the next 20 seconds...")
                    sb.sleep(20)
                
                # --- NEW: Infinite Scroll Loop to Load All Flights ---
                print("🔄 Starting infinite scroll to load all flights into the DOM...")
                
                last_flight_count = 0
                no_change_count = 0
                
                while no_change_count < 5:  # Stop if the flight count doesn't increase after 5 scroll attempts
                    # Scroll down progressively
                    sb.execute_script("window.scrollBy(0, 3000);")
                    sb.sleep(2.5)  # Allow time for new AJAX elements to render
                    
                    # Count currently visible flights
                    current_html = sb.get_page_source()
                    current_soup = BeautifulSoup(current_html, 'html.parser')
                    current_flights = len(current_soup.find_all('div', class_='flightItem'))
                    print(f"Scrolled... Loaded flights so far: {current_flights}")
                    
                    if current_flights > last_flight_count:
                        last_flight_count = current_flights
                        no_change_count = 0  # Reset counter if new items found
                    else:
                        no_change_count += 1  # Increment if no new entries appeared
                        
                    # Optional: nudge the page up and down to trigger stubborn event listeners
                    if no_change_count > 2:
                        sb.execute_script("window.scrollBy(0, -500);")
                        sb.sleep(1)
                        sb.execute_script("window.scrollBy(0, 500);")
                
                print(f"🛑 Finished scrolling. Total flights captured in DOM: {last_flight_count}")
                
                # Grab final complete DOM source code
                dom_html = sb.get_page_source()
                soup = BeautifulSoup(dom_html, 'html.parser')
                
                # Re-check live content title
                print("✅ Live Page Title:", soup.title.text if soup.title else "N/A")
                
                flight_elements = soup.select(".flight-det, .tuple, [class*='flightItem']")
                
                # Save raw HTML for manual inspection if selectors ever go stale
                with open('page_dump.html', 'w', encoding='utf-8') as f:
                    for i in flight_elements:
                        f.write(str(i))
                        
                flight_element = soup.find_all('div', class_='flightItem')
                if not flight_element:
                    raise RuntimeError(
                        "No 'flightItem' divs found — selectors are likely stale. "
                        "Check page_dump.html for the current markup."
                    )
                    
                extracted_flights = []
                for flight in flight_element:
                    airline_elem = flight.find('span', class_='i-b text ellipsis')
                    airline = airline_elem.text.strip() if airline_elem else "N/A"
                    
                    fl_no_elem = flight.find('p', class_='fl-no')
                    fl_no = fl_no_elem.text.strip() if fl_no_elem else "N/A"
                    
                    dep_time_elem = flight.find('div', autom='departureTimeLabel')
                    dep_time = dep_time_elem.div.contents[0].strip() if (dep_time_elem and dep_time_elem.div) else "N/A"
                    
                    cities = flight.find_all('p', class_='city')
                    dep_city = cities[0].get('title', '').strip() if len(cities) > 0 else "N/A"
                    arr_city = cities[1].get('title', '').strip() if len(cities) > 1 else "N/A"
                    
                    arr_time_elem = flight.find('p', autom='arrivalTimeLabel')
                    arr_time = arr_time_elem.text.strip() if arr_time_elem else "N/A"
                    
                    duration_elem = flight.find('p', autom='durationLabel')
                    duration = duration_elem.text.strip() if duration_elem else "N/A"
                    
                    stops_elem = flight.find('span', class_='cursor-default')
                    stops = stops_elem.text.strip() if stops_elem else "N/A"
                    
                    price_elem = flight.find('div', class_='fare-summary-tooltip')
                    price = price_elem.text.strip() if price_elem else "N/A"
                    
                    extracted_flights.append({
                        'Airline': airline,
                        'Flight Number': fl_no,
                        'Departure Time': dep_time,
                        'Departure City': dep_city,
                        'Arrival Time': arr_time,
                        'Arrival City': arr_city,
                        'Duration': duration,
                        'Stops': stops,
                        'Price (INR)': price
                    })

                # --- pandas export + diagnostics ---
                if extracted_flights:
                    df = pd.DataFrame(extracted_flights)
                    print("\nShape:", df.shape)
                    print(df.head())
                    
                    na_rate = (df == "N/A").mean().sort_values(ascending=False)
                    print("\nN/A rate per column:")
                    print(na_rate)
                    
                    if na_rate.max() > 0.5:
                        print("⚠️ Warning: some fields are mostly N/A — those selectors likely need updating.")
                    df.to_csv(f'all_flights{number}.csv', index=False, encoding='utf-8')
                    print("\n✅ Saved all_flights.csv")
                    number=number+1
                else:
                    print("❌ No flights extracted — nothing to save.")
