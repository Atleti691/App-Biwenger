# Mejoras pendientes

## Playoffs por el título y ascenso — 3 de octubre de 2026

Reglas confirmadas: torneo independiente en cada división; seis primeros de la general J24 y ganador del play-in 7.º–8.º en J25. Liguilla todos contra todos J26–32, siete participantes, seis partidos y un descanso por manager. Total neto con todos los ajustes. Cuatro primeros a Final Four: 1.º–4.º y 2.º–3.º; semifinales ida J34, vuelta J35; final y tercer puesto J36 (este calendario sustituye el final inicial en J35). Desempate de eliminatorias por mejor posición en la general.

Segunda: cuatro ascensos; 1.º y 2.º de la general al finalizar J36; campeón del título (si ya es ascenso directo, pasa al subcampeón; si ambos ascienden directamente, al 3.º de la general); ganador del playoff de ascenso. Sus cruces se fijan en la general J35: 3.º–6.º y 4.º–5.º en J36, final J37.

Preparados pantalla por división, leyendas, play-in, calendario natural y cálculo de cruces con total neto y datos cerrados. Pendientes de confirmar: puntos por victoria/empate/derrota en la liguilla; exclusión o sustitución en el playoff de ascenso de quien ascienda por el título; resolución de un empate también en la clasificación general. No conceder ascensos duplicados ni resolver estos casos por orden alfabético.

Última precisión: la liguilla usa solo puntos APP. Falta confirmar si esto sustituye también el total neto en las eliminatorias, y si la liguilla concede 3/1/0 por victoria/empate/derrota. Confirmado: excluir del playoff de ascenso a quien ascienda por el título y dar su plaza al siguiente de la general. Como se conoce al finalizar J36, los cruces de ascenso no son definitivos antes de resolver esa exclusión.

Confirmación final y aplicación: todos los partidos usan solo puntos APP. Liguilla 3/1/0, sin puntos por descanso. Calculados automáticamente play-in, 21 cruces de la liguilla, su clasificación, semifinales J34–35, final y tercer puesto J36, y ascenso J36–37. La clasificación general para acceder/desempatar conserva el total de la liga. Ascensos sin duplicados: excluir también a quienes ya tengan ascenso directo al resolver los cruces; sustituirlos por siguientes elegibles de la clasificación J35. Datos abiertos, ausentes o empates no resueltos mantienen los resultados pendientes. Nuevos cálculos sin migración ni modificación de las puntuaciones guardadas.

## Sustituir el icono de Zarra por el boceto original — 3 de octubre de 2026

Pendiente de aplicar. Rafael ha elegido el icono compacto de la derecha del boceto original: balón de cuero clásico entrando en la red. Sustituir el distintivo vectorial de copa y balón que se puso después, tanto en Torneos como en Estadísticas y sus leyendas. Mantener tamaño y alineación uniformes.

Referencia original: `C:/Users/Rafael/.codex/generated_images/01a0859b-c393-7391-bc0a-8a23a0e100a9/exec-4679efb0-e072-4ff8-b9da-f3e244a95053.png`. Usar la variante compacta de la derecha, no la imagen completa con ambos diseños.

Aplicado el 3 de octubre: icono aislado con la herramienta integrada de imágenes, guardado en `core/assets/tournaments/zarra-icon-original.png` y conectado mediante la plantilla compartida a Torneos, Estadísticas y leyendas. Prompt de edición: extraer únicamente el icono compacto de la derecha (balón de cuero clásico entrando en la red), conservar su diseño y colores, eliminar el escudo izquierdo y el texto, y dar fondo transparente con margen uniforme.

## Icono del playoff de descenso — 3 de octubre de 2026

Pendiente para la próxima tanda de mejoras. Rafael quiere dos puños con guantes de boxeo enfrentados, uno azul y otro rojo, como distintivo del playoff de descenso, en lugar del icono actual de dos equipos enfrentados. Aplicarlo de forma consistente en Estadísticas y Torneos, manteniendo el tamaño, la alineación y la etiqueta accesible «Playoff de descenso». No sustituir el distintivo del descenso directo.

## Quinielas y porras: distinguir vacío de cero — 3 de octubre de 2026

Pendiente de aplicar más adelante, según petición de Rafael.

- En Introducir datos, las casillas vacías de quinielas y porras se marcarán en rojo para indicar que el manager no las ha hecho.
- El valor explícito `0` indica que sí ha participado, pero no ha acertado ninguna; no debe marcarse en rojo.
- Conservar la diferencia entre casilla vacía y cero al guardar y volver a cargar la jornada; no convertir automáticamente los valores vacíos en cero.
- Comprobar ambas columnas con vacío, cero y valores positivos. No cambiar las reglas de puntuación.

## Revisión de logos e iconos — 1 de octubre de 2026

Solicitadas por Rafael. Pendientes de revisar; no implican cambios ya aplicados.

- Torneos Liga Amigos: revisar por qué no aparece el logo de Champions League y corregir su presentación.
- Torneos Liga Amigos: revisar el logo de Zarra; confirmar el diseño definitivo y que aparezca en la tarjeta del torneo.
- Estadísticas Liga: revisar que el icono de Zarra aparezca en las clasificaciones correspondientes.
- Descenso: sustituir la flecha roja simple por un distintivo más cuidado y claro. Propuesta para valorar: una insignia roja con una escalera descendente; evitar confundir un pulgar hacia abajo con una valoración negativa del manager.
- Playoff de descenso: revisar el icono de espadas cruzadas, que tampoco gusta. Propuesta para valorar: un distintivo de eliminatoria con dos equipos enfrentados.
- Mantener la alineación y un tamaño uniforme de los distintivos de las clasificaciones.

## Aplicación — 2 de octubre de 2026

Rafael ha pedido aplicar estas mejoras. Cambios preparados en el repositorio:

- Champions: logo existente conectado a tarjeta, leyenda y clasificación de Torneos.
- Zarra: distintivo vectorial de copa y balón clásico conectado a Torneos y Estadísticas.
- Descenso: insignia roja con escalera descendente, en lugar de la flecha simple.
- Playoff: distintivo con dos equipos enfrentados, en lugar de espadas cruzadas.
- Tamaños y alineación compartidos; nombres accesibles y títulos en los iconos.

Comprobadas la renderización de ambas plantillas y la sintaxis JavaScript. Pendiente de subir y comprobar visualmente en la aplicación desplegada.
