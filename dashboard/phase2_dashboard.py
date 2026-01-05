import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# Ensure we can import modules from /src
# ------------------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from pz_model import (
    PZParams,
    simulate_pz,
    p_dynamic_from_fs,
    fs_ratio_for_employees,
)

# ------------------------------------------------------------
# Export path for saved runs
# ------------------------------------------------------------
EXPORT_PATH = Path("outputs/csv/phase2_dashboard_runs.csv")
EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------
# Helpers: trajectory simulation to compute "time to FS thresholds"
# ------------------------------------------------------------
def run_path_until(months: int, params: PZParams, A0: float, m0: float, BC0: float, FS0: float) -> pd.DataFrame:
    rm = params.r_annual / 12.0

    A = float(A0)
    m = float(m0)
    employees = int(params.employees0)
    BC = float(BC0)
    FS = float(FS0)

    hires = 0
    last_hire_month = -10_000

    rows = []

    for t in range(1, months + 1):
        costs = employees * params.cost_per_employee + params.other_fixed_costs
        # Revenue controlled by a fixed monthly growth rate (option 2)
        rev0 = A0 * m0
        revenue = rev0 * ((1.0 + params.rev_growth) ** (t - 1))

        interest = rm * (BC + FS)
        U = revenue + interest - costs

        fs_cov_before = (FS / costs) if costs > 0 else np.inf

        # Effective p (auto policy or manual override)
        if 0.0 <= params.p_override <= 1.0:
            p_eff = params.p_override
        elif params.use_dynamic_p:
            p_eff = p_dynamic_from_fs(fs_cov_before, p4_max=params.p4_max)
        else:
            p_eff = 0.30

        p_eff = max(0.0, min(1.0, p_eff))
        impact = 0.0
        rd = 0.0

        if U > 0:
            # Split U into investment pool (BC) and Planet Zero pool (BPZ)
            BC_in = p_eff * U
            BPZ_in = (1.0 - p_eff) * U
            BC += BC_in

            # Survival Fund contribution (FS)
            FS_in = params.fs_pct_of_bpz * BPZ_in
            FS += FS_in

            # Remaining BPZ split
            BPZ_rem = (1.0 - params.fs_pct_of_bpz) * BPZ_in
            impact = params.impact_pct_of_bpz_rem * BPZ_rem
            internal = params.internal_pct_of_bpz_rem * BPZ_rem
            rd = params.rd_pct_of_internal * internal

            # People dynamics
            # Option 2: revenue growth is exogenous, so keep A constant
            A = A


            # Margin dynamics (small learning effect)
            m = m

            # Hiring (only when FS is comfortably above target)
            fs_ratio = fs_ratio_for_employees(employees)
            fs_target = fs_ratio * costs
            if (t - last_hire_month) >= params.hire_cooldown_months:
                if FS >= params.hire_trigger_buffer * fs_target:
                    employees += 1
                    hires += 1
                    last_hire_month = t

        costs_after = employees * params.cost_per_employee + params.other_fixed_costs
        fs_cov_after = (FS / costs_after) if costs_after > 0 else np.inf

        rows.append({
            "month": t,
            "people": A,
            "margin_per_person": m,
            "employees": employees,
            "monthly_costs": costs_after,
            "revenue": revenue,
            "interest": interest,
            "utility": U,
            "p_to_investment": p_eff,
            "impact_spend": impact,
            "rd_spend": rd,
            "BC": BC,
            "FS": FS,
            "FS_coverage_months": fs_cov_after,
        })

    return pd.DataFrame(rows)


def first_crossing_month(traj: pd.DataFrame, threshold: float):
    hit = traj.index[traj["FS_coverage_months"] >= threshold].tolist()
    if not hit:
        return None
    return int(traj.loc[hit[0], "month"])


def fmt_month(m):
    return "No llega" if m is None else f"Mes {m}"


# ------------------------------------------------------------
# Cache: makes live updates fast when you move sliders around
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_run(horizon: int, params_dict: dict, A0: float, m0: float, BC0: float, FS0: float):
    params = PZParams(**params_dict)
    traj = run_path_until(horizon, params, A0, m0, BC0, FS0)
    t3 = first_crossing_month(traj, 3.0)
    t6 = first_crossing_month(traj, 6.0)
    t12 = first_crossing_month(traj, 12.0)
    summary = simulate_pz(months=horizon, p_to_bc=0.30, params=params, B0=BC0, FS0=FS0)
    return traj, t3, t6, t12, summary


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.set_page_config(page_title="Planet Zero — Phase 2 (Viabilidad)", layout="wide")

st.title("Planet Zero — Dashboard de Viabilidad (Phase 2)")
st.caption("Esto NO es un dashboard de ‘reparto bonito’. Es una prueba dura: ¿el proyecto sobrevive con estos números?")

with st.expander("Cómo usar este dashboard (léelo una vez y listo)", expanded=True):
    st.markdown(
        """
### Qué estás probando aquí
Este panel responde una pregunta simple:

**Con X personas activas y €Y de margen neto por persona/mes, el sistema puede:**
- pagar la operación,
- construir un colchón (FS),
- y escalar sin morir?

### Qué significa ‘margen neto por persona’
**m (margen por persona/mes)** es lo que te queda *después de los costos variables del producto* (pasarela, hosting por usuario, soporte directo por usuario, etc.).  
**NO incluye salarios ni costos fijos**.  
Por eso aún necesitamos los **costos operativos**: son los que determinan si existe utilidad positiva (U) para repartir.

### Cómo leer el resultado
- **FS (colchón)** se mide en “meses de costos cubiertos”.  
  - FS ≥ 3 → sobrevives
  - FS ≥ 6 → estable
  - FS ≥ 12 → resiliente

Si el sistema **no llega** a esos umbrales, el producto/escala no es viable bajo estas hipótesis.

### Consejo práctico
Empieza con:
- A0 = tu base realista (o 100 si estás explorando)
- m0 = un margen conservador
- churn 3% y ratio entradas 1.0 (neutral)

Luego juega con:
- subir m0 (mejor pricing / producto)
- subir A0 (mejor distribución)
- o reducir costos
"""
    )

with st.expander("Glosario rápido de parámetros (para humanos)", expanded=False):
    st.markdown(
        """
- **A0 (Personas iniciales):** clientes/usuarios activos al inicio.  
- **m0 (Margen neto por persona/mes):** lo que queda por usuario luego de costos variables.  
- **Empleados/costos:** costos fijos mensuales de operar (salarios + herramientas + legal, etc.).  
- **Churn (%):** % de usuarios que se van cada mes.  
- **Entradas vs churn:**  
  - 1.0 = reemplazas los que se van (A se mantiene)  
  - <1.0 = te achicas  
  - >1.0 = creces  
- **BC0:** capital inicial invertido (genera interés desde el día 1).  
- **FS0:** colchón inicial (caja/bonos líquidos para sobrevivir).  
- **Política automática (p depende de FS):** cuando el colchón es bajo, el sistema invierte menos / prioriza supervivencia; cuando está sano, invierte más.  
- **% a FS:** dentro del dinero de Planet Zero (BPZ), cuánto se guarda como colchón.  
- **% a Impacto:** cuánto se usa en impacto inmediato (visible).  
- **% a R&D:** cuánto se invierte en mejorar producto (lento pero acumulativo).
"""
    )

# ---------------- Sidebar (live inputs) ----------------
with st.sidebar:
    st.header("Inputs principales")

    horizon = st.selectbox(
        "Horizonte de simulación",
        [24, 60, 120],
        index=0,
        format_func=lambda x: f"{x} meses",
        help="Cuánto tiempo simulamos. 24=2 años, 60=5 años, 120=10 años."
    )

    A0 = st.number_input(
        "Personas iniciales (A0)",
        min_value=0,
        max_value=1_000_000,
        value=100,
        step=10,
        help="Cuántos clientes/usuarios activos tienes al inicio."
    )

    m0 = st.number_input(
        "Margen neto por persona / mes (€) (m0)",
        min_value=0.0,
        max_value=100_000.0,
        value=25.0,
        step=1.0,
        help="Lo que te queda por usuario/mes después de costos variables. NO incluye salarios ni costos fijos."
    )

    st.divider()
    st.subheader("Costos operativos (fijos)")

    employees0 = st.number_input(
        "Empleados iniciales",
        min_value=0,
        max_value=200,
        value=2,
        step=1,
        help="Cuántas personas en nómina desde el mes 1."
    )

    cost_per_employee = st.number_input(
        "Costo mensual por empleado (€)",
        min_value=0.0,
        max_value=1_000_000.0,
        value=1000.0,
        step=50.0,
        help="Costo total (no solo salario): salario + impuestos + beneficios + todo."
    )

    other_fixed_costs = st.number_input(
        "Otros costos fijos mensuales (€)",
        min_value=0.0,
        max_value=1_000_000.0,
        value=0.0,
        step=50.0,
        help="Software, legal, contabilidad, oficinas, servidores fijos, etc."
    )

    st.divider()
    st.subheader("Crecimiento (simple)")


    rev_growth = st.slider(
        "Crecimiento mensual del ingreso (%)",
        -0.50, 0.50, 0.00, 0.01,
        help="Controla cómo crece o cae el ingreso total mes a mes. 0% = ingreso plano. 2% = crece 2% mensual."
    ) 


    churn = st.slider(
        "Churn mensual (%)",
        0.0, 0.30, 0.03, 0.005,
        help="Porcentaje de usuarios que se van cada mes."
    )

    acq_ratio = st.slider(
        "Entradas vs churn (1.0 = reemplazas churn)",
        0.0, 2.0, 1.0, 0.05,
        help="Si es 1.0, entra la misma cantidad que se va. >1 creces, <1 te achicas."
    )

    st.divider()
    st.subheader("Capital inicial (si existe)")

    BC0 = st.number_input(
        "Capital inicial invertido (BC0) (€)",
        min_value=0.0,
        max_value=10_000_000.0,
        value=0.0,
        step=500.0,
        help="Dinero invertido desde el día 1 que genera interés."
    )

    FS0 = st.number_input(
        "Colchón inicial de supervivencia (FS0) (€)",
        min_value=0.0,
        max_value=10_000_000.0,
        value=0.0,
        step=500.0,
        help="Caja/bonos líquidos para sobrevivir desde el día 1."
    )

    st.divider()
    st.subheader("Reglas de reparto (Planet Zero)")

    fs_pct_of_bpz = st.slider(
        "% de BPZ que va al colchón (FS)",
        0.0, 0.90, 0.30, 0.05,
        help="De la parte BPZ (no invertida), cuánto se guarda como colchón."
    )

    impact_pct_of_bpz_rem = st.slider(
        "% de lo restante que va a impacto",
        0.0, 1.0, 0.60, 0.05,
        help="Después de guardar FS, cuánto de lo restante se gasta en impacto inmediato."
    )
    internal_pct_of_bpz_rem = 1.0 - impact_pct_of_bpz_rem

    rd_pct_of_internal = st.slider(
        "% de operación interna que va a R&D",
        0.0, 1.0, 0.60, 0.05,
        help="De lo interno (no impacto), cuánto va a mejorar producto/tecnología."
    )

    st.divider()
    st.subheader("Política de inversión (automática)")

    use_auto = st.checkbox(
        "Usar política automática (p depende del colchón FS)",
        value=True,
        help="Cuando el colchón es bajo, el sistema invierte menos; cuando es alto, invierte más."
    )

    p4_max = st.slider(
        "Máximo % hacia inversión cuando el sistema está sano",
        0.0, 0.90, 0.70, 0.05,
        help="Tope de cuánto puede ir a inversión (BC) cuando el sistema está muy estable."
    )

    override = st.checkbox(
        "Fijar manualmente % hacia inversión (override)",
        value=False,
        help="Si lo activas, ignoras la política automática y fijas p."
    )

    p_override = -1.0
    if override:
        p_override = st.slider(
            "% fijo hacia inversión (BC)",
            0.0, 0.90, 0.30, 0.05,
            help="Porcentaje fijo de utilidad positiva que se va a inversión (BC)."
        )

# ---------------- Build params_dict (cache-friendly) ----------------
params_dict = dict(
    r_annual=0.04,

    employees0=int(employees0),
    cost_per_employee=float(cost_per_employee),
    other_fixed_costs=float(other_fixed_costs),

    fs_pct_of_bpz=float(fs_pct_of_bpz),
    impact_pct_of_bpz_rem=float(impact_pct_of_bpz_rem),
    internal_pct_of_bpz_rem=float(internal_pct_of_bpz_rem),
    rd_pct_of_internal=float(rd_pct_of_internal),

    churn_rate=float(churn),
    acq_churn_ratio=float(acq_ratio),
    k_acq=0.20,

    use_dynamic_p=bool(use_auto),
    p_override=float(p_override),
    p4_max=float(p4_max),

    rev_growth=float(rev_growth),

)

# ---------------- Run simulation (live) ----------------
traj, t3, t6, t12, summary = cached_run(
    int(horizon),
    params_dict,
    float(A0),
    float(m0),
    float(BC0),
    float(FS0),
)

# ---------------- Outputs: viability ----------------
st.subheader("Resultado principal (viabilidad)")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("¿Llega a 3 meses de colchón (FS)?", "Sí" if t3 is not None else "No", fmt_month(t3))
with c2:
    st.metric("¿Llega a 6 meses de colchón (FS)?", "Sí" if t6 is not None else "No", fmt_month(t6))
with c3:
    st.metric("¿Llega a 12 meses de colchón (FS)?", "Sí" if t12 is not None else "No", fmt_month(t12))

st.caption(
    f"Meses con utilidad positiva: {summary['pct_months_U_pos']*100:.1f}%  |  "
    f"Utilidad promedio/mes: €{summary['avg_U']:.1f}"
)

# Quick sanity callout (if utility mostly negative)
if summary["pct_months_U_pos"] < 0.25:
    st.warning(
        "La utilidad es negativa la mayor parte del tiempo. En este escenario, el sistema no tiene combustible real para crecer. "
        "Sube margen (m0), sube A0, baja costos o agrega capital inicial."
    )

st.divider()

# ---------------- End-state snapshot ----------------
st.subheader("Resumen al final del horizonte")
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Colchón final (FS)", f"€{summary['FS_end']:.0f}")
with k2:
    st.metric("Capital invertido final (BC)", f"€{summary['BC_end']:.0f}")
with k3:
    st.metric("Impacto acumulado", f"€{summary['impact_cum_end']:.0f}")
with k4:
    st.metric("Empleados al final", f"{int(summary['employees_end'])}")

st.divider()

# ---------------- Charts ----------------
st.subheader("Evolución del sistema")
left, right = st.columns(2)
with left:
    st.write("**Colchón (FS) en meses de cobertura**")
    st.line_chart(traj.set_index("month")[["FS_coverage_months"]])
with right:
    st.write("**Utilidad mensual e Impacto mensual**")
    st.line_chart(traj.set_index("month")[["utility", "impact_spend"]])

st.divider()

# ---------------- Table ----------------
st.subheader("Tabla (últimos meses)")
st.dataframe(traj.tail(min(36, len(traj))), use_container_width=True)

# ------------------------------------------------------------
# Save scenario
# ------------------------------------------------------------
st.divider()
st.subheader("Guardar escenario (para comparar después)")

colA, colB = st.columns([2, 1])
with colA:
    scenario_name = st.text_input(
        "Nombre del escenario (ej: 'SaaS 25€ - 100 users - base')",
        value="",
        placeholder="Ponle un nombre claro para recordarlo"
    )
    notes = st.text_area(
        "Notas (opcional)",
        value="",
        placeholder="Ej: producto B2B, margen conservador, churn alto por categoría, etc."
    )

with colB:
    export_btn = st.button("Exportar escenario", type="secondary")

if export_btn:
    if not scenario_name.strip():
        scenario_name = f"Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenario_name": scenario_name.strip(),
        "notes": notes.strip(),

        "horizon_months": int(horizon),
        "A0_people": float(A0),
        "m0_margin_per_person": float(m0),

        "BC0_initial_capital": float(BC0),
        "FS0_initial_survival": float(FS0),

        "employees0": int(employees0),
        "cost_per_employee": float(cost_per_employee),
        "other_fixed_costs": float(other_fixed_costs),

        "churn_rate": float(churn),
        "acq_churn_ratio": float(acq_ratio),
        "k_acq": float(params_dict["k_acq"]),

        "use_auto_policy": bool(use_auto),
        "p4_max": float(p4_max),
        "override_enabled": bool(override),
        "p_override": float(p_override),

        "fs_pct_of_bpz": float(fs_pct_of_bpz),
        "impact_pct_of_bpz_rem": float(impact_pct_of_bpz_rem),
        "internal_pct_of_bpz_rem": float(internal_pct_of_bpz_rem),
        "rd_pct_of_internal": float(rd_pct_of_internal),

        "time_to_FS3_months": None if t3 is None else int(t3),
        "time_to_FS6_months": None if t6 is None else int(t6),
        "time_to_FS12_months": None if t12 is None else int(t12),

        "FS_end": float(summary["FS_end"]),
        "BC_end": float(summary["BC_end"]),
        "impact_cum_end": float(summary["impact_cum_end"]),
        "employees_end": int(summary["employees_end"]),
        "A_end": float(summary["A_end"]),
        "m_end": float(summary["m_end"]),
        "avg_U": float(summary["avg_U"]),
        "pct_months_U_pos": float(summary["pct_months_U_pos"]),
        "p_eff_last": float(summary.get("p_eff_last", np.nan)),
        "phase_final": summary.get("phase_final", None),
        "fs_coverage_months_final": float(summary["fs_coverage_months_final"]),
    }

    df_new = pd.DataFrame([record])

    if EXPORT_PATH.exists():
        df_old = pd.read_csv(EXPORT_PATH)
        df_out = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_out = df_new

    df_out.to_csv(EXPORT_PATH, index=False)
    st.success(f"Escenario guardado en: {EXPORT_PATH.as_posix()}")

    st.caption("Últimos escenarios guardados:")
    st.dataframe(df_out.tail(10), use_container_width=True)

# ------------------------------------------------------------
# Download CSV button (always available if file exists)
# ------------------------------------------------------------
st.divider()
st.subheader("Descargar historial de escenarios")

if EXPORT_PATH.exists():
    csv_bytes = EXPORT_PATH.read_bytes()
    st.download_button(
        label="Descargar CSV (historial de escenarios)",
        data=csv_bytes,
        file_name="phase2_dashboard_runs.csv",
        mime="text/csv",
        help="Baja el historial de pruebas para compararlo en Excel/Sheets."
    )
    st.caption(f"Archivo actual: {EXPORT_PATH.as_posix()}")
else:
    st.info("Aún no hay escenarios guardados. Usa **Exportar escenario** al menos una vez.")
