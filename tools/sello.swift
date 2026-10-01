// El candado del buzón del móvil: AES-256-GCM con CryptoKit (de Apple, viene con macOS).
// Lo usa nube.py; build.sh lo compila universal2 y va dentro del .app (Contents/Frameworks/sello).
//
//   sello cerrar < (32 bytes de llave + datos)          -> 12 bytes de iv + cifrado + 16 de etiqueta
//   sello abrir  < (32 bytes de llave + iv+cifrado+tag)  -> datos (solo para las pruebas)
//
// La llave entra por la entrada estándar, nunca por argumentos (que se ven con `ps`).
// El formato de salida es el que espera crypto.subtle en el móvil (store.js, unseal).
import CryptoKit
import Foundation

let input = FileHandle.standardInput.readDataToEndOfFile()
guard CommandLine.arguments.count == 2, input.count >= 32 else {
    FileHandle.standardError.write("uso: sello cerrar|abrir < llave+datos\n".data(using: .utf8)!)
    exit(2)
}
let key = SymmetricKey(data: input.prefix(32))
let data = input.dropFirst(32)
do {
    switch CommandLine.arguments[1] {
    case "cerrar":
        let box = try AES.GCM.seal(data, using: key)   // nonce aleatorio de 12 bytes
        FileHandle.standardOutput.write(box.combined!)
    case "abrir":
        let box = try AES.GCM.SealedBox(combined: data)
        FileHandle.standardOutput.write(try AES.GCM.open(box, using: key))
    default:
        exit(2)
    }
} catch {
    FileHandle.standardError.write("no se puede\n".data(using: .utf8)!)
    exit(1)
}
