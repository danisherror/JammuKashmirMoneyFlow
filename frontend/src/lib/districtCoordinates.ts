/**
 * Map marker positions for the 20 districts of J&K, keyed by the district
 * `code` used in `backend/database/seeds.py`.
 *
 * Each point is the district headquarters town, used only to place a marker on
 * the map — no figures are derived from it.
 *
 * Primary source (checked 2026-11-23): Directorate of Economics & Statistics,
 * J&K, "Socio-Economic Profile of Jammu & Kashmir 2008", Statistical
 * Information, Table No 5 "Coordinates of District Headquarters of J&K State"
 * (PDF p. 177; the table cites the Ecology, Environment & Remote Sensing Deptt.,
 * Bemina, Srinagar):
 * https://ecostatjk.nic.in/pdf/publications/socoeconomic/2007-08.pdf
 * The table gives degrees/minutes/seconds; they are converted to decimal
 * degrees here, rounded to 4 places.
 *
 * Five rows of that table are wrong by 4–25 km, so those districts use a
 * cross-checked town point instead (see the comment on each):
 *  - Pulwama and Shopian: the table swaps their longitudes. The official
 *    district site puts Pulwama at 33.8831 N, 74.9209 E
 *    (https://pulwama.gov.in/?p=22578).
 *  - Samba, Poonch, Kulgam: the table's point is 8–23 km from the town. No
 *    official point found yet; the town coordinates on Wikipedia are used.
 */
export const DISTRICT_COORDINATES: Record<string, [number, number]> = {
  // Jammu Division
  JMU: [32.7208, 74.8617], // Jammu — Table 5: 32°43'15" 74°51'42"
  // Samba — Table 5 says 32°38'08" 74°53'47", which is next to Jammu city,
  // ~23 km from Samba town. Town point: https://en.wikipedia.org/wiki/Samba,_Jammu_and_Kashmir
  SMB: [32.57, 75.12],
  KTH: [32.3711, 75.5239], // Kathua — Table 5: 32°22'16" 75°31'26"
  UDH: [32.9228, 75.1347], // Udhampur — Table 5: 32°55'22" 75°08'05"
  RSI: [33.0814, 74.8339], // Reasi — Table 5: 33°04'53" 74°50'02"
  RJR: [33.3711, 74.3047], // Rajouri — Table 5: 33°22'16" 74°18'17"
  // Poonch — Table 5 says 33°40'03" (≈11 km south of the town).
  // Town point: https://en.wikipedia.org/wiki/Poonch_(town)
  PNC: [33.7703, 74.0925],
  DDA: [33.1417, 75.5439], // Doda — Table 5: 33°08'30" 75°32'38"
  KWT: [33.3119, 75.765], // Kishtwar — Table 5: 33°18'43" 75°45'54"
  RMB: [33.2417, 75.2403], // Ramban — Table 5: 33°14'30" 75°14'25"
  // Kashmir Division
  SGR: [34.0733, 74.8136], // Srinagar — Table 5: 34°04'24" 74°48'49"
  BDG: [34.015, 74.7197], // Budgam — Table 5: 34°00'54" 74°43'11"
  ANN: [33.7303, 75.1503], // Anantnag — Table 5: 33°43'49" 75°09'01"
  // Kulgam — Table 5 says 33°33'35" (≈9 km south of the town).
  // Town point: https://en.wikipedia.org/wiki/Kulgam
  KLG: [33.64, 75.02],
  // Pulwama — Table 5 latitude 33°52'29"; longitude from https://pulwama.gov.in/?p=22578
  // (Table 5's 74°49'56" belongs to Shopian).
  PWM: [33.8747, 74.9209],
  // Shopian — Table 5 latitude 33°42'58"; longitude from
  // https://en.wikipedia.org/wiki/Shopian (Table 5's 74°53'56" belongs to Pulwama).
  SPN: [33.7161, 74.8333],
  BRM: [34.21, 74.3386], // Baramulla — Table 5: 34°12'36" 74°20'19"
  BNP: [34.4189, 74.6378], // Bandipora — Table 5: 34°25'08" 74°38'16"
  KPW: [34.5253, 74.26], // Kupwara — Table 5: 34°31'31" 74°15'36"
  GNB: [34.2169, 74.7806], // Ganderbal — Table 5: 34°13'01" 74°46'50"
}
