/**
 * Map marker positions for the 20 districts of J&K, keyed by the district
 * `code` used in `backend/database/seeds.py`.
 *
 * Each point is the approximate location of the district headquarters town,
 * used only to place a marker on the map — no figures are derived from it.
 * Source: not yet checked against an official gazetteer (e.g. Survey of India);
 * values are approximate to ~0.01°. See todo.md.
 */
export const DISTRICT_COORDINATES: Record<string, [number, number]> = {
  // Jammu Division
  JMU: [32.7266, 74.857], // Jammu
  SMB: [32.5625, 75.1199], // Samba
  KTH: [32.3863, 75.5173], // Kathua
  UDH: [32.916, 75.1416], // Udhampur
  RSI: [33.081, 74.832], // Reasi
  RJR: [33.378, 74.309], // Rajouri
  PNC: [33.77, 74.093], // Poonch
  DDA: [33.145, 75.548], // Doda
  KWT: [33.311, 75.766], // Kishtwar
  RMB: [33.242, 75.237], // Ramban
  // Kashmir Division
  SGR: [34.0837, 74.7973], // Srinagar
  BDG: [34.02, 74.718], // Budgam
  ANN: [33.7311, 75.1487], // Anantnag
  KLG: [33.645, 75.019], // Kulgam
  PWM: [33.874, 74.899], // Pulwama
  SPN: [33.717, 74.834], // Shopian
  BRM: [34.209, 74.343], // Baramulla
  BNP: [34.417, 74.65], // Bandipora
  KPW: [34.526, 74.255], // Kupwara
  GNB: [34.227, 74.774], // Ganderbal
}
