import pandas as pd
import numpy as np
import geopandas as gpd
import folium
import os

# --- CONFIGURATION ET RÉFÉRENTIELS ---
VALID_NEIGHBORHOODS = [
    "Cambridgeport", "East Cambridge", "Mid-Cambridge", "North Cambridge",
    "Riverside", "Area 4", "West Cambridge", "Peabody", "Inman/Harrington",
    "Highlands", "Agassiz", "MIT", "Strawberry Hill"
] # [cite: 49]

def audit_qualite(df):
    """Calcule les indicateurs de qualité demandés [cite: 29-36]."""
    total = len(df)
    stats = {}
    
    # Complétude [cite: 30]
    for col in ['File Number', 'Crime', 'Neighborhood']:
        stats[f'Complétude {col}'] = (df[col].notna().sum() / total) * 100
    
    # Unicité File Number [cite: 31]
    stats['Unicité File Number'] = (df['File Number'].nunique() / total) * 100
    
    # Doublons exacts [cite: 32]
    stats['Taux Doublons'] = (df.duplicated().sum() / total) * 100
    
    # Dates invalides [cite: 33]
    dates_rep = pd.to_datetime(df['Date of Report'], errors='coerce')
    stats['Dates Invalides (%)'] = (dates_rep.isna().sum() / total) * 100
    
    # Incohérences temporelles [cite: 34]
    dates_crime = pd.to_datetime(df['Crime Date Time'], errors='coerce')
    incoherents = (dates_rep < dates_crime).sum()
    stats['Incohérences Temporelles (%)'] = (incoherents / total) * 100
    
    # Reporting Area non conforme [cite: 35]
    valides_ra = df['Reporting Area'].astype(str).str.match(r'^\d+(-\d+)?$', na=False)
    stats['Reporting Area Non Conforme (%)'] = ((~valides_ra).sum() / total) * 100
    
    return pd.Series(stats)

def main():
    # --- 1. PROFILAGE ET EXPLORATION --- [cite: 14]
    print("--- Étape 1: Profilage ---")
    df = pd.read_csv('crime_reports_broken.csv')
    print(f"Lignes: {len(df)}") # [cite: 17]
    print(df.dtypes) # [cite: 18]
    print(df.isna().sum()) # [cite: 19]

    # --- 2. AUDIT INITIAL --- [cite: 26]
    print("\n--- Étape 2: Audit Initial ---")
    audit_initial = audit_qualite(df)
    print(audit_initial)

    # --- 3. TRAITEMENT --- [cite: 39]
    print("\n--- Étape 3: Traitement ---")
    df_clean = df.copy() # [cite: 40]
    
    # Doublons et Crime null [cite: 42, 43]
    df_clean = df_clean.drop_duplicates()
    df_clean = df_clean.dropna(subset=['Crime'])
    
    # Dates [cite: 44, 45]
    df_clean['Date of Report'] = pd.to_datetime(df_clean['Date of Report'], errors='coerce')
    df_clean['Crime Date Time'] = pd.to_datetime(df_clean['Crime Date Time'], errors='coerce')
    df_clean = df_clean.dropna(subset=['Date of Report'])
    df_clean = df_clean[df_clean['Date of Report'] >= df_clean['Crime Date Time']]
    
    # Quartiers valides [cite: 47, 49]
    df_clean = df_clean[df_clean['Neighborhood'].isin(VALID_NEIGHBORHOODS)]
    
    # Enrichissement reporting_area_group [cite: 55]
    # Extraction du groupe (ex: 1109 -> 11) via division entière
    df_clean['reporting_area_group'] = pd.to_numeric(df_clean['Reporting Area'], errors='coerce') // 100
    df_clean = df_clean[df_clean['reporting_area_group'] >= 0] # [cite: 56]
    
    df_clean.to_csv('crime_reports_clean.csv', index=False) # [cite: 57]

    # --- 4. MONITORING --- [cite: 58]
    print("\n--- Étape 4: Monitoring ---")
    audit_final = audit_qualite(df_clean)
    comparison = pd.DataFrame({'Avant': audit_initial, 'Après': audit_final})
    print(comparison)

    # --- 5. CARTOGRAPHIE --- [cite: 62]
    if os.path.exists('BOUNDARY_CDDNeighborhoods.geojson'):
        print("\n--- Étape 5: Cartographie ---")
        # Agrégation [cite: 65]
        crimes_par_quartier = df_clean.groupby('Neighborhood').size().reset_index(name='Nb_Crimes')
        
        # Chargement Géo [cite: 69]
        gdf = gpd.read_file('BOUNDARY_CDDNeighborhoods.geojson')

        # Jointure [cite: 71] (Vérifiez les noms de colonnes dans votre GeoJSON)
        # On suppose que le nom du quartier est dans la colonne 'name' du GeoJSON
        merged = gdf.merge(crimes_par_quartier, left_on='NAME', right_on='Neighborhood')

        # Carte Choroplèthe
        m = folium.Map(location=[42.3736, -71.1097], zoom_start=13)
        folium.Choropleth(
            geo_data=gdf,
           name="choropleth",
           data=crimes_par_quartier,
           columns=["Neighborhood", "Nb_Crimes"],
           # 2. Modifie la fin de cette ligne avec le bon nom de colonne
           key_on="feature.properties.NAME", 
           fill_color="YlOrRd",
           legend_name="Nombre de crimes par quartier"
        ).add_to(m)
        
        m.save('map.html') # [cite: 77]
        print("Carte générée: map.html")

if __name__ == "__main__":
    main()