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
]

def audit_qualite(df):
    """Calcule les indicateurs de qualité demandés."""
    total = len(df)
    stats = {}
    
    # Complétude
    for col in ['File Number', 'Crime', 'Neighborhood']:
        stats[f'Complétude {col}'] = (df[col].notna().sum() / total) * 100
    
    # Unicité File Number
    stats['Unicité File Number'] = (df['File Number'].nunique() / total) * 100
    
    # Doublons exacts 
    stats['Taux Doublons'] = (df.duplicated().sum() / total) * 100
    
    # Dates invalides
    dates_rep = pd.to_datetime(df['Date of Report'], errors='coerce')
    stats['Dates Invalides (%)'] = (dates_rep.isna().sum() / total) * 100
    
    # Incohérences temporelles
    dates_crime = pd.to_datetime(df['Crime Date Time'], errors='coerce')
    incoherents = (dates_rep < dates_crime).sum()
    stats['Incohérences Temporelles (%)'] = (incoherents / total) * 100
    
    # Reporting Area non conforme 
    valides_ra = df['Reporting Area'].astype(str).str.match(r'^\d+(-\d+)?$', na=False)
    stats['Reporting Area Non Conforme (%)'] = ((~valides_ra).sum() / total) * 100
    
    return pd.Series(stats)

def main():
    # --- 1. PROFILAGE ET EXPLORATION ---
    print("--- Étape 1: Profilage ---")
    df = pd.read_csv('crime_reports_broken.csv')
    print(f"Lignes: {len(df)}") 
    print(df.dtypes) 
    print(df.isna().sum()) 

    # --- 2. AUDIT INITIAL ---
    print("\n--- Étape 2: Audit Initial ---")
    audit_initial = audit_qualite(df)
    print(audit_initial)

    # --- 3. TRAITEMENT ---
    print("\n--- Étape 3: Traitement ---")
    df_clean = df.copy() 
    
    # Doublons et Crime null
    df_clean = df_clean.drop_duplicates()
    df_clean = df_clean.dropna(subset=['Crime'])
    
    # Dates 
    df_clean['Date of Report'] = pd.to_datetime(df_clean['Date of Report'], errors='coerce')
    df_clean['Crime Date Time'] = pd.to_datetime(df_clean['Crime Date Time'], errors='coerce')
    df_clean = df_clean.dropna(subset=['Date of Report'])
    df_clean = df_clean[df_clean['Date of Report'] >= df_clean['Crime Date Time']]
    
    # Quartiers valides
    df_clean = df_clean[df_clean['Neighborhood'].isin(VALID_NEIGHBORHOODS)]
    
    # Enrichissement reporting_area_group 
    # Extraction du groupe (ex: 1109 -> 11) via division entière
    df_clean['reporting_area_group'] = pd.to_numeric(df_clean['Reporting Area'], errors='coerce') // 100
    df_clean = df_clean[df_clean['reporting_area_group'] >= 0] 
    
    df_clean.to_csv('crime_reports_clean.csv', index=False) 

    # --- 4. MONITORING --- [cite: 58]
    print("\n--- Étape 4: Monitoring ---")
    audit_final = audit_qualite(df_clean)
    comparison = pd.DataFrame({'Avant': audit_initial, 'Après': audit_final})
    print(comparison)

# --- 5. CARTOGRAPHIE ---
    if os.path.exists('BOUNDARY_CDDNeighborhoods.geojson'):
        print("\n--- Étape 5: Cartographie ---")
        
        # 1. Agrégation
        crimes_par_quartier = df_clean.groupby('Neighborhood').size().reset_index(name='Nb_Crimes')
        # Dictionnaire de correspondance CSV -> GeoJSON
        corrections_noms = {
          'Agassiz': 'Baldwin',
         'Area 4': 'The Port',
          'Highlands': 'Cambridge Highlands',
          'Inman/Harrington': 'Wellington-Harrington',
          'MIT': 'Area 2/MIT',
          'Peabody': 'Neighborhood Nine'
        }

        crimes_par_quartier['Neighborhood'] = crimes_par_quartier['Neighborhood'].replace(corrections_noms)        
        # 2. Chargement Géo
        gdf = gpd.read_file('BOUNDARY_CDDNeighborhoods.geojson')
        
        colonne_geo = 'NAME' 
        # 3. Jointure : on utilise 'merged' pour TOUT faire ensuite
        merged = gdf.merge(crimes_par_quartier, left_on=colonne_geo, right_on='Neighborhood')
        
        # 4. Carte de base
        m = folium.Map(location=[42.3736, -71.1097], zoom_start=13)
        
        # 5. Création du Choroplèthe (en utilisant 'merged' comme source unique)
        choro = folium.Choropleth(
            geo_data=merged,
            name="choropleth",
            data=merged,
            columns=[colonne_geo, "Nb_Crimes"],
            key_on=f"feature.properties.{colonne_geo}",
            fill_color="YlOrRd",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Nombre de crimes par quartier"
        ).add_to(m)
        
        # 6. Ajout du Tooltip (info-bulle au survol)
        choro.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=[colonne_geo, 'Nb_Crimes'], # Les données à lire
                aliases=['Quartier :', 'Crimes enregistrés :'], # Le texte affiché à l'écran
                style="background-color: white; color: #333; font-family: arial; font-size: 13px; padding: 8px;"
            )
        )

        m.save('map.html')
        print("Carte générée: map.html")

if __name__ == "__main__":
    main()

