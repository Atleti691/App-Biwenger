# Seguimiento de correos para repartir puntos VIP

## Despliegue

1. Aplicar migraciones: `python manage.py migrate` (crea `0025_correopenalizacionvip`).
2. En Render, añadir `BREVO_WEBHOOK_TOKEN` con un secreto largo y aleatorio. No es la contraseña SMTP y no debe guardarse en Git ni enviarse a los managers.
3. En Brevo, crear un webhook transaccional con destino `https://liga-amigos-xi.onrender.com/webhooks/brevo/vip/` y autenticación Bearer con ese mismo secreto. Seleccionar entrega, apertura, clic, rebotes, bloqueo, dirección inválida y aplazamiento.
4. Hacer una prueba controlada desde la aplicación y comprobar que el estado cambia de «Enviado · entrega sin confirmar» a «Entrega confirmada por Brevo» o al error real.

Los correos siguen usando el SMTP ya configurado. Cada intento lleva `X-Mailin-custom: vip_attempt:<UUID>`; el receptor comprueba autenticación, referencia y dirección de destino. No se asignan eventos solo por dirección, porque un manager puede tener varios correos de distintos partidos.

Sin configurar el webhook, funcionan el registro de envío y los recordatorios, pero la entrega queda sin confirmar. Los correos enviados antes de esta mejora no tienen referencia individual y se muestran «Sin registro de envío», no como entregados ni como fallidos. No se consulta retrospectivamente Brevo por aproximación.

## Uso

En Gestión de partidos VIP, junto a cada acertante aparece un desplegable con el último estado, destino, fecha e historial de avisos. La lista distingue reparto ejecutado y pendiente. Consulta no muestra direcciones ni este historial.

«Recordar a acertantes pendientes» envía avisos solo a quienes aún no han repartido puntos. «Recordar pendientes · últimas 24 h» se habilita únicamente en las últimas 24 horas del plazo de reparto, antes del cierre. Es un botón manual, no una automatización. No se envía dos veces el aviso final por doble pulsación; los fallos de envío se pueden reintentar. No se envían recordatorios vencido el plazo.

Entrega confirmada significa aceptación por el servidor destinatario, no que el correo esté en la bandeja principal ni que lo haya leído una persona. Una ausencia de confirmación no demuestra que no haya llegado.

Documentación de referencia: https://developers.brevo.com/docs/transactional-webhooks
