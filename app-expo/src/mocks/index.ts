/** Datos mock mientras el backend no está conectado en cada pantalla */
export const mockBars = [
  { id: "bar1", name: "Cerveseria La Espuma", lat: 41.3266, lng: 2.0946, address: "C/ Major 12, El Prat", rating: 4.4, lastScan: "hace 2 días", styles: ["Hazy IPA", "Lager", "Stout"] },
  { id: "bar2", name: "El Grifo Dorado", lat: 41.3809, lng: 2.1735, address: "C/ Ferran 8, Barcelona", rating: 4.1, lastScan: "hoy", styles: ["West Coast IPA", "Sour"] },
  { id: "bar3", name: "Bar Llúpol", lat: 41.4036, lng: 2.1744, address: "Gràcia, Barcelona", rating: 4.7, lastScan: "hace 5 h", styles: ["Imperial Stout", "Saison"] },
];

export const mockScanItems = [
  { line: "Garage Beer Co - Soup - Hazy IPA", brewery: { id: "b1", name: "Garage Beer Co", raw: "", score: 96 }, style: { id: "s2", name: "Hazy IPA", raw: "", score: 98 }, beer_name: "Soup", confidence: 0.94 },
  { line: "Basqueland Imparable - West Coast IPA", brewery: { id: "b2", name: "Basqueland", raw: "", score: 91 }, style: { id: "s3", name: "West Coast IPA", raw: "", score: 95 }, beer_name: "Imparable", confidence: 0.89 },
  { line: "La Pirata Black Block", brewery: { id: "b4", name: "La Pirata", raw: "", score: 93 }, style: null, beer_name: "Black Block", confidence: 0.71 },
];

export const mockStats = { styles: 23, breweries: 41, bars: 12 };

export const mockTimeline = [
  { date: "2026-07-08", items: 6 },
  { date: "2026-06-30", items: 5 },
  { date: "2026-06-18", items: 7 },
];
