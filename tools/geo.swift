// Busca sitios con el buscador de Apple Maps (MKLocalSearch): gratis, sin cuenta
// de desarrollador y sin permiso de ubicacion. Lo llama sitios.py. Copia de
// ~/Projects/ig-saved/tools/geo.swift + "cat" (la categoria de Apple: Restaurant,
// Cafe, Nightlife...), que da el tipo del sitio sin IA. Se compila universal2 en build.sh.
//   echo '[{"id":"x","q":"Casa Lucio, Madrid"}]' | swift tools/geo.swift
// Devuelve una linea JSON por consulta: {"id","ok","c":[hasta 5 candidatos]}; cada
// candidato {"name","addr","lat","lng","city","country","poi","calle"}. Apple los ordena por
// relevancia; sitios.py elige (nombre + ciudad). Si hay varios "Casa Pepe", el primero
// es el mas conocido, que es lo que quiere Nacho.
import Foundation
import MapKit

// "ciudad": true -> CLGeocoder (la ciudad a secas: MKLocalSearch confunde "Ibiza" con la
// calle Ibiza de Madrid, porque busca alrededor del Mac). "cerca": [lat, lng] -> buscar el
// local en 30 km alrededor de ese punto (su ciudad), no alrededor del Mac.
struct Q: Decodable { let id: String; let q: String; let ciudad: Bool?; let cerca: [Double]? }

let data = FileHandle.standardInput.readDataToEndOfFile()
let qs = (try? JSONDecoder().decode([Q].self, from: data)) ?? []

func out(_ d: [String: Any]) {
    let j = try! JSONSerialization.data(withJSONObject: d, options: [])
    print(String(data: j, encoding: .utf8)!)
    fflush(stdout)
}

var intentos = 0
func buscar(_ i: Int) {
    if i >= qs.count { exit(0) }
    let q = qs[i]
    if q.ciudad == true {
        CLGeocoder().geocodeAddressString(q.q) { marks, err in
            if let p = marks?.first, let loc = p.location {
                out(["id": q.id, "ok": true, "c": [["name": p.locality ?? p.name ?? "", "lat": loc.coordinate.latitude,
                     "lng": loc.coordinate.longitude, "addr": "", "city": p.locality ?? "", "country": p.isoCountryCode ?? "",
                     "poi": false, "calle": false]]])
            } else {
                // "vacio": true = Apple contesto que no hay nada (no es un fallo de red)
                let code = (err as NSError?)?.code ?? 0
                out(["id": q.id, "ok": false, "err": err.map { "\($0.localizedDescription)" } ?? "sin resultados",
                     "vacio": err == nil || (code == CLError.geocodeFoundNoResult.rawValue)])
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.3) { buscar(i + 1) }
        }
        return
    }
    let req = MKLocalSearch.Request()
    req.naturalLanguageQuery = q.q
    if let c = q.cerca, c.count == 2 {
        req.region = MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: c[0], longitude: c[1]),
                                        latitudinalMeters: 60000, longitudinalMeters: 60000)
    }
    req.resultTypes = [.pointOfInterest, .address]
    MKLocalSearch(request: req).start { resp, err in
        // Apple frena (~50 busquedas/min, MKError 3 = loadingThrottled): esperar y repetir la misma
        if let e = err as? MKError, e.code == .loadingThrottled, intentos < 6 {
            intentos += 1
            DispatchQueue.main.asyncAfter(deadline: .now() + 30) { buscar(i) }
            return
        }
        intentos = 0
        if let items = resp?.mapItems, !items.isEmpty {
            let c: [[String: Any]] = items.prefix(5).map { it in
                let p = it.placemark
                return ["name": it.name ?? "", "lat": p.coordinate.latitude, "lng": p.coordinate.longitude,
                        "addr": [p.thoroughfare, p.subThoroughfare].compactMap { $0 }.joined(separator: " "),
                        "city": p.locality ?? "", "country": p.isoCountryCode ?? "",
                        "poi": it.pointOfInterestCategory != nil, "calle": p.thoroughfare != nil,
                        "cat": it.pointOfInterestCategory?.rawValue ?? ""]
            }
            out(["id": q.id, "ok": true, "c": c])
        } else {
            let code = (err as? MKError)?.code
            out(["id": q.id, "ok": false, "err": err.map { "\($0.localizedDescription)" } ?? "sin resultados",
                 "vacio": err == nil || code == .placemarkNotFound])
        }
        // Apple limita la frecuencia: una cada 1,3 s no pasa de ~46 por minuto
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.3) { buscar(i + 1) }
    }
}

DispatchQueue.main.async { buscar(0) }
RunLoop.main.run()
