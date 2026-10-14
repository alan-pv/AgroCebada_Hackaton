# Resumen de experimentos del modelo generalizable

Generado por `scripts/generalizable_experimentos.py` en 85 minutos. Objetivo rend (SIAP, sobre cosechada). RMSE de nivel en t/ha, media de 10 repeticiones. La métrica principal es la ponderada por superficie sembrada en todos los municipios.

## Curva de exclusión, RMSE de nivel ponderado por superficie (principal)

| modelo | 0 | 20 | 40 | 50 | 60 | 80 |
|---|---|---|---|---|---|---|
| media_global | 0.504 | 0.535 | 0.586 | 0.594 | 0.600 | 0.625 |
| media_estatal | 0.451 | 0.481 | 0.611 | 0.644 | 0.782 | 0.811 |
| idw_vecinos | 0.349 | 0.428 | 0.550 | 0.560 | 0.565 | 0.570 |
| kriging_vecinos | 0.309 | 0.381 | 0.527 | 0.566 | 0.574 | 0.584 |
| simple_a_tmax | 0.334 | 0.378 | 0.475 | 0.490 | 0.492 | 0.522 |
| simple_b_elev | 0.437 | 0.502 | 0.613 | 0.631 | 0.649 | 0.705 |
| simple_c_tmax_prec | 0.272 | 0.304 | 0.449 | 0.506 | 0.529 | 0.572 |
| simple_d_tmax_prec_durica | 0.287 | 0.329 | 0.500 | 0.592 | 0.650 | 0.608 |
| simple_e_tmax_prec_estado | 0.305 | 0.364 | 0.551 | 0.541 | 0.669 | 0.707 |
| kriging_residuos_simple_a_tmax | 0.293 | 0.369 | 0.440 | 0.438 | 0.431 | 0.445 |
| kriging_residuos_simple_b_elev | 0.302 | 0.409 | 0.507 | 0.521 | 0.523 | 0.558 |
| kriging_residuos_simple_c_tmax_prec | 0.269 | 0.304 | 0.421 | 0.464 | 0.483 | 0.526 |
| kriging_residuos_simple_d_tmax_prec_durica | 0.279 | 0.322 | 0.476 | 0.571 | 0.615 | 0.557 |
| kriging_residuos_simple_e_tmax_prec_estado | 0.287 | 0.367 | 0.539 | 0.532 | 0.663 | 0.710 |
| ridge_ambiente | 0.302 | 0.402 | 0.594 | 0.662 | 0.704 | 0.736 |
| lasso_ambiente | 0.302 | 0.339 | 0.535 | 0.612 | 0.626 | 0.704 |

## Curva de exclusión, RMSE de nivel sin ponderar

| modelo | 0 | 20 | 40 | 50 | 60 | 80 |
|---|---|---|---|---|---|---|
| media_global | 0.488 | 0.514 | 0.564 | 0.579 | 0.597 | 0.645 |
| media_estatal | 0.410 | 0.433 | 0.507 | 0.530 | 0.612 | 0.664 |
| idw_vecinos | 0.349 | 0.404 | 0.494 | 0.510 | 0.527 | 0.571 |
| kriging_vecinos | 0.343 | 0.395 | 0.492 | 0.518 | 0.527 | 0.600 |
| simple_a_tmax | 0.457 | 0.471 | 0.507 | 0.511 | 0.509 | 0.593 |
| simple_b_elev | 0.509 | 0.540 | 0.609 | 0.623 | 0.633 | 0.725 |
| simple_c_tmax_prec | 0.426 | 0.441 | 0.486 | 0.515 | 0.527 | 0.564 |
| simple_d_tmax_prec_durica | 0.434 | 0.454 | 0.522 | 0.575 | 0.601 | 0.569 |
| simple_e_tmax_prec_estado | 0.426 | 0.455 | 0.518 | 0.546 | 0.586 | 0.661 |
| kriging_residuos_simple_a_tmax | 0.411 | 0.449 | 0.463 | 0.459 | 0.451 | 0.485 |
| kriging_residuos_simple_b_elev | 0.419 | 0.489 | 0.530 | 0.548 | 0.553 | 0.594 |
| kriging_residuos_simple_c_tmax_prec | 0.427 | 0.454 | 0.479 | 0.496 | 0.504 | 0.532 |
| kriging_residuos_simple_d_tmax_prec_durica | 0.432 | 0.464 | 0.516 | 0.565 | 0.583 | 0.537 |
| kriging_residuos_simple_e_tmax_prec_estado | 0.426 | 0.470 | 0.516 | 0.541 | 0.581 | 0.654 |
| ridge_ambiente | 0.469 | 0.507 | 0.572 | 0.617 | 0.631 | 0.731 |
| lasso_ambiente | 0.460 | 0.471 | 0.539 | 0.585 | 0.568 | 0.594 |

## Municipios con mediana de al menos 1 000 ha sembradas, ponderado

| modelo | 0 | 20 | 40 | 50 | 60 | 80 |
|---|---|---|---|---|---|---|
| media_global | 0.511 | 0.543 | 0.595 | 0.601 | 0.606 | 0.627 |
| media_estatal | 0.456 | 0.487 | 0.618 | 0.651 | 0.795 | 0.821 |
| idw_vecinos | 0.351 | 0.434 | 0.561 | 0.571 | 0.575 | 0.574 |
| kriging_vecinos | 0.307 | 0.383 | 0.537 | 0.578 | 0.586 | 0.587 |
| simple_a_tmax | 0.314 | 0.363 | 0.472 | 0.488 | 0.490 | 0.514 |
| simple_b_elev | 0.428 | 0.498 | 0.616 | 0.635 | 0.654 | 0.705 |
| simple_c_tmax_prec | 0.246 | 0.283 | 0.446 | 0.507 | 0.532 | 0.572 |
| simple_d_tmax_prec_durica | 0.262 | 0.311 | 0.499 | 0.598 | 0.659 | 0.612 |
| simple_e_tmax_prec_estado | 0.285 | 0.352 | 0.552 | 0.533 | 0.672 | 0.706 |
| kriging_residuos_simple_a_tmax | 0.274 | 0.356 | 0.438 | 0.436 | 0.429 | 0.439 |
| kriging_residuos_simple_b_elev | 0.285 | 0.396 | 0.507 | 0.522 | 0.523 | 0.556 |
| kriging_residuos_simple_c_tmax_prec | 0.239 | 0.280 | 0.414 | 0.461 | 0.482 | 0.525 |
| kriging_residuos_simple_d_tmax_prec_durica | 0.250 | 0.301 | 0.472 | 0.575 | 0.623 | 0.559 |
| kriging_residuos_simple_e_tmax_prec_estado | 0.262 | 0.352 | 0.538 | 0.524 | 0.666 | 0.709 |

## Regla de decisión contra el kriging

Victorias en 10 repeticiones. p de la permutación de las variables ambientales (n = 99), solo para el contendiente fijado de antemano, el mejor simple de cada B y el modelo final.

| B_km | modelo | principal | kriging | victorias | sin_ponderar | kriging_sin_ponderar | victorias_sin_ponderar | p | regla |
|---|---|---|---|---|---|---|---|---|---|
| 0 | simple_a_tmax | 0.334 | 0.309 | 2 | 0.457 | 0.343 | 0 |  |  |
| 0 | simple_b_elev | 0.437 | 0.309 | 0 | 0.509 | 0.343 | 0 |  |  |
| 0 | simple_c_tmax_prec | 0.272 | 0.309 | 10 | 0.426 | 0.343 | 0 | 0.01 | acepta |
| 0 | simple_d_tmax_prec_durica | 0.287 | 0.309 | 7 | 0.434 | 0.343 | 0 |  |  |
| 0 | simple_e_tmax_prec_estado | 0.305 | 0.309 | 5 | 0.426 | 0.343 | 0 |  |  |
| 0 | kriging_residuos_simple_a_tmax | 0.293 | 0.309 | 7 | 0.411 | 0.343 | 0 | 0.02 | acepta |
| 0 | kriging_residuos_simple_b_elev | 0.302 | 0.309 | 7 | 0.419 | 0.343 | 0 |  |  |
| 0 | kriging_residuos_simple_c_tmax_prec | 0.269 | 0.309 | 10 | 0.427 | 0.343 | 0 |  |  |
| 0 | kriging_residuos_simple_d_tmax_prec_durica | 0.279 | 0.309 | 9 | 0.432 | 0.343 | 0 |  |  |
| 0 | kriging_residuos_simple_e_tmax_prec_estado | 0.287 | 0.309 | 8 | 0.426 | 0.343 | 0 |  |  |
| 0 | ridge_ambiente | 0.302 | 0.309 | 4 | 0.469 | 0.343 | 0 |  |  |
| 0 | lasso_ambiente | 0.302 | 0.309 | 4 | 0.460 | 0.343 | 0 |  |  |
| 50 | simple_a_tmax | 0.490 | 0.566 | 10 | 0.511 | 0.518 | 8 | 0.01 | acepta |
| 50 | simple_b_elev | 0.631 | 0.566 | 0 | 0.623 | 0.518 | 0 |  |  |
| 50 | simple_c_tmax_prec | 0.506 | 0.566 | 10 | 0.515 | 0.518 | 7 | 0.01 | acepta |
| 50 | simple_d_tmax_prec_durica | 0.592 | 0.566 | 3 | 0.575 | 0.518 | 0 |  |  |
| 50 | simple_e_tmax_prec_estado | 0.541 | 0.566 | 5 | 0.546 | 0.518 | 4 |  |  |
| 50 | kriging_residuos_simple_a_tmax | 0.438 | 0.566 | 10 | 0.459 | 0.518 | 10 |  |  |
| 50 | kriging_residuos_simple_b_elev | 0.521 | 0.566 | 10 | 0.548 | 0.518 | 0 |  |  |
| 50 | kriging_residuos_simple_c_tmax_prec | 0.464 | 0.566 | 10 | 0.496 | 0.518 | 10 |  |  |
| 50 | kriging_residuos_simple_d_tmax_prec_durica | 0.571 | 0.566 | 7 | 0.565 | 0.518 | 0 |  |  |
| 50 | kriging_residuos_simple_e_tmax_prec_estado | 0.532 | 0.566 | 5 | 0.541 | 0.518 | 4 |  |  |
| 50 | ridge_ambiente | 0.662 | 0.566 | 0 | 0.617 | 0.518 | 0 |  |  |
| 50 | lasso_ambiente | 0.612 | 0.566 | 0 | 0.585 | 0.518 | 0 |  |  |

Modelo final: **kriging_residuos_simple_a_tmax**. simple_a_tmax pasa la regla en B = 50. Promedio de la métrica principal en B = 0 y 50: kriging_vecinos 0.438, simple_a_tmax 0.412, kriging_residuos_simple_a_tmax 0.366.

## Robustez: por DDR y sin cifras repetidas del SIAP

| modelo | ddr completos B=0 pond | ddr completos B=0 sin pond | espacial_buffer completos B=0 pond | espacial_buffer completos B=0 sin pond | espacial_buffer completos B=50 pond | espacial_buffer completos B=50 sin pond | espacial_buffer sin_repetidos B=0 pond | espacial_buffer sin_repetidos B=0 sin pond | espacial_buffer sin_repetidos B=50 pond | espacial_buffer sin_repetidos B=50 sin pond |
|---|---|---|---|---|---|---|---|---|---|---|
| media_global | 0.534 | 0.513 | 0.504 | 0.488 | 0.594 | 0.579 | 0.592 | 0.617 | 0.693 | 0.724 |
| media_estatal | 0.497 | 0.479 | 0.451 | 0.410 | 0.644 | 0.530 | 0.532 | 0.537 | 0.826 | 0.755 |
| idw_vecinos | 0.446 | 0.436 | 0.349 | 0.349 | 0.560 | 0.510 | 0.402 | 0.433 | 0.657 | 0.655 |
| kriging_vecinos | 0.503 | 0.523 | 0.309 | 0.343 | 0.566 | 0.518 | 0.402 | 0.443 | 0.683 | 0.693 |
| simple_a_tmax | 0.373 | 0.473 | 0.334 | 0.457 | 0.490 | 0.511 | 0.422 | 0.586 | 0.592 | 0.669 |
| simple_b_elev | 0.481 | 0.538 | 0.437 | 0.509 | 0.631 | 0.623 | 0.546 | 0.623 | 0.799 | 0.794 |
| simple_c_tmax_prec | 0.305 | 0.441 | 0.272 | 0.426 | 0.506 | 0.515 | 0.365 | 0.530 | 0.658 | 0.673 |
| simple_d_tmax_prec_durica | 0.334 | 0.469 | 0.287 | 0.434 | 0.592 | 0.575 | 0.374 | 0.526 | 0.659 | 0.683 |
| simple_e_tmax_prec_estado | 0.494 | 0.543 | 0.305 | 0.426 | 0.541 | 0.546 | 0.380 | 0.527 | 0.825 | 0.840 |
| kriging_residuos_simple_a_tmax | 0.393 | 0.463 | 0.293 | 0.411 | 0.438 | 0.459 | 0.383 | 0.499 | 0.558 | 0.598 |
| kriging_residuos_simple_b_elev | 0.427 | 0.527 | 0.302 | 0.419 | 0.521 | 0.548 | 0.414 | 0.483 | 0.678 | 0.691 |
| kriging_residuos_simple_c_tmax_prec | 0.359 | 0.468 | 0.269 | 0.427 | 0.464 | 0.496 | 0.369 | 0.510 | 0.630 | 0.655 |
| kriging_residuos_simple_d_tmax_prec_durica | 0.375 | 0.485 | 0.279 | 0.432 | 0.571 | 0.565 | 0.371 | 0.516 | 0.631 | 0.665 |
| kriging_residuos_simple_e_tmax_prec_estado | 0.532 | 0.566 | 0.287 | 0.426 | 0.532 | 0.541 | 0.382 | 0.523 | 0.801 | 0.821 |

## Importancia por bloque (métrica principal)

Condicional: aumento al revolver el bloque en el ridge con los cuatro bloques. Marginal: mejora de un ridge con solo ese bloque sobre la media global.

| buffer_km | bloque | rmse_completo | rmse_completo_bloque_revuelto | aumento_condicional | p_condicional | rmse_media_global | rmse_solo_bloque | mejora_marginal | p_marginal |
|---|---|---|---|---|---|---|---|---|---|
| 0 | temperatura | 0.273 | 0.393 | 0.120 | 0.010 | 0.504 | 0.337 | 0.167 | 0.010 |
| 0 | lluvia | 0.273 | 0.379 | 0.106 | 0.010 | 0.504 | 0.404 | 0.100 | 0.010 |
| 0 | topografia | 0.273 | 0.312 | 0.038 | 0.020 | 0.504 | 0.434 | 0.070 | 0.010 |
| 0 | suelo | 0.273 | 0.268 | -0.005 | 0.640 | 0.504 | 0.553 | -0.049 | 0.900 |
| 50 | temperatura | 0.607 | 0.771 | 0.164 | 0.010 | 0.594 | 0.562 | 0.032 | 0.010 |
| 50 | lluvia | 0.607 | 0.706 | 0.099 | 0.010 | 0.594 | 0.653 | -0.059 | 0.070 |
| 50 | topografia | 0.607 | 0.660 | 0.052 | 0.010 | 0.594 | 0.687 | -0.093 | 0.720 |
| 50 | suelo | 0.607 | 0.531 | -0.076 | 1.000 | 0.594 | 0.900 | -0.307 | 1.000 |

## Clima del año (RMSE por fila, sin ponderar)

En el esquema espacial las anomalías reconocen el año. El esquema por año es la prueba de pronóstico.

| esquema | familia | modelo | rmse |
|---|---|---|---|
| espacial | base | kriging_vecinos | 0.682 |
| espacial | ubicacion | lgbm_ubicacion | 0.669 |
| espacial | con cosecha del año | lgbm_ubicacion_anomalias | 0.611 |
| espacial | con cosecha del año | lgbm_ubicacion_indicadoras_anio | 0.608 |
| espacial | con cosecha del año | kriging_mas_efecto_estado_anio | 0.596 |
| espacial | con cosecha del año | idw_vecinos_anio | 0.588 |
| anio | base | media_propia_tendencia | 0.632 |
| anio | clima del año | propia_mas_anomalia_ridge | 0.636 |
| anio | clima del año | propia_mas_anomalia_lgbm | 0.647 |
