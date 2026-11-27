# Prueba en Windows (WSL2) con AWS

**Español** · English below

## Propósito

Repetir la prueba de Dixi Tower en Windows sin tener una PC con Windows: una máquina Windows Server 2025 en AWS con virtualización anidada, que es lo que necesita WSL2.

## Pasos

1. `AWS_PROFILE=mi-perfil AWS_REGION=us-east-2 tests/windows/crear.sh`. Crea la máquina (`m8i.xlarge`, unos 0,40 USD por hora), con escritorio remoto y SSH abiertos solo para tu IP, espera la contraseña de `Administrator` y te dice cómo entrar.
2. Entra por escritorio remoto (en macOS, con Windows App) y, si quieres trabajar por SSH, pega el bloque de PowerShell que imprime el guion.
3. Sigue la sección «En Windows (WSL2)» del [manual](../../docs/manual.es.md#en-windows-wsl2). En Windows Server, WSL se instala con el `.msi` de [sus versiones](https://github.com/microsoft/WSL/releases).
4. Comprueba: `dixi-tower doctor` reconoce WSL, el panel abre en Edge, un agente arranca, y al terminar su turno llega un aviso de Windows que abre el agente al hacer clic. Los avisos solo se ven si el panel se levantó desde tu sesión de escritorio remoto, no desde SSH.
5. `AWS_PROFILE=mi-perfil AWS_REGION=us-east-2 tests/windows/borrar.sh`. Borra la máquina, su disco, el grupo de seguridad y la llave.

La llave, la contraseña y los ids se guardan en `tests/windows/.estado/`, fuera de git, y se borran con `borrar.sh`.

## Windows test (WSL2) on AWS

To repeat the Windows test without a Windows PC: `crear.sh` launches a Windows Server 2025 instance with nested virtualization (about USD 0.40/hour), open to your IP only; follow "On Windows (WSL2)" in the [manual](../../docs/manual.md#on-windows-wsl2); `borrar.sh` deletes everything. Both need `AWS_PROFILE` and `AWS_REGION`.

## Links

- [Manual](../../docs/manual.md)
- [Hoja de ruta](../../ROADMAP.md)
