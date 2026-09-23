# W1 - Business Intelligence IIB423T-1
## Fuentes públicas Chile 2020-2024 + brief ajustado

Este paquete acompaña el workshop **W1 - Discovering questions worth investigating**. Conserva una estructura de fuentes reproducible para que los estudiantes trabajen con información pública oficial.

### Contenido

- `W1_IIB423T-1_Brief_and_Rubric_Tomas_Fontecilla.pdf`: brief/rúbrica, idéntico al documento base salvo instructor y fechas del curso trimestral coordinadas.
- `FUENTES.csv` / `FUENTES.json`: inventario fuente-año, institución, página oficial, URL directa cuando existe y nota de descarga.
- `descargar_datos.py`: descarga automáticamente los recursos con URL binaria estable.
- carpetas `Urgencias/`, `REM/`, `Establecimientos/`, `GRD/`, `cartografia_censo_2024/`: destino de datos y notas por fuente.

### Descargar datos

Linux/macOS:
```bash
./descargar_datos.sh
```

Windows PowerShell:
```powershell
./descargar_datos.ps1
```

O directamente:
```bash
python descargar_datos.py
```

Para abrir además los catálogos dinámicos (REM, GRD, Censo):
```bash
python descargar_datos.py --abrir-catalogos
```

### Por qué las bases crudas no vienen incrustadas en este ZIP

Se conserva la descarga desde la **fuente oficial** en vez de redistribuir copias que pueden quedar desactualizadas. Además, REM, GRD y la cartografía nacional pueden ser archivos grandes y sus portales publican algunos binarios mediante catálogos dinámicos. El paquete deja trazabilidad de fuente/año y permite que cada equipo retenga el original que efectivamente descargó, coherente con la exigencia del propio workshop de documentar fuente, versión y fecha de recuperación.

### Cobertura solicitada

- Urgencias: 2020, 2021, 2022, 2023, 2024.
- REM: 2020, 2021, 2022, 2023, 2024.
- Establecimientos: 2020, 2021, 2022, 2023, 2024, incluyendo diccionarios.
- GRD / GRD-IR: 2020, 2021, 2022, 2023, 2024.
- Cartografía Censo 2024: cobertura Chile.

### Nota de fuente GRD

GRD se obtiene desde **FONASA Datos Abiertos**. FONASA forma parte del sector salud, pero el portal de descarga no es el repositorio DEIS/MINSAL. Esto coincide con el punto de partida indicado en el brief.
