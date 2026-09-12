import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import math as m
#================================================================================
#                                   PAGE TITLE
#================================================================================
st.set_page_config(page_title= "Well Performance Dashboard", layout = "wide")
st.title("CSS and Pump Monitoring Dashboard")
st.divider()

#region CONSTANTS
#================================================================================
#                                   CONSTANTS
#================================================================================
geothermal_gradient = 0.025 # C/m
surface_earth_temp = 15 # C
wellbore_loss_factor = 0.0002 # per meter
water_specific_heat = 4.18 # kJ/kg C
latent_heat_vap = 2257.0 # kJ/kg
res_thickness = 15.0 # meters (thickness of the oil sand)
rock_density = 2200.0 # kg/m^3 (average sandstone density)
radial_expansion_rate = 4
res_heat_capacity = 1.2 # kJ/kg C
caprock_heat_loss_rate = 0.02 # 2% heat loss per day during soaking amd production
base_oil_viscosity = 10000.0 # cP (extremely thick unheated oil)
alpha = 0.35 # Steam volume to temperature scaling coefficient ($\alpha$)
lambd = 0.15 # Soak heat transfer efficiency factor ($\lambda$)
k_cooling = 0.04 # Reservoir cooling/dissipation constant ($k$)
ea_over_r = 4500.0 # Activation energy over gas constant ($E_a / R$) for Arrhenius equation
q_base = 15.0 # Baseline production rate (bbl/day)
max_upstroke = 80
min_downstroke = 25
distortion_scaling_factor = 45 #for fluid pound
theoretical_displacement = 0.01 #max fillage
n = 200 #number of pts used to generate pump stroke
pi = m.pi
oil_price_per_bbl = 7500.0 # Assumed market price
daily_opex = 300000.0 # Daily cost to run the pump, pay crew, maintain site
#endregion

#region INITIALIZATION
#================================================================================
#                                 INITIALIZATION
#================================================================================
if 'simulation_day' not in st.session_state:
    st.session_state.simulation_day = 0
if 'current_stage' not in st.session_state:
    st.session_state.current_stage = "Stage 1: Steam Injection"
if 'cumulative_oil' not in st.session_state:
    st.session_state.cumulative_oil = 0.0
if 'current_reservoir_temp' not in st.session_state:
    st.session_state.current_reservoir_temp = surface_earth_temp
if 'cycle_sor' not in st.session_state:
    st.session_state.cycle_sor = 0.0
if 'current_viscosity' not in st.session_state:
    st.session_state.current_viscosity = base_oil_viscosity
if 'total_steam_injected' not in st.session_state:
    st.session_state.total_steam_injected = 0.0
if 'radial_penetration' not in st.session_state:
    st.session_state.radial_penetration = 0.0
if 'peak_reservoir_temp' not in st.session_state:
    st.session_state.peak_reservoir_temp = surface_earth_temp
if 'daily_oil_rate' not in st.session_state:
    st.session_state.daily_oil_rate = 0.0
if 'daily_revenue' not in st.session_state:
    st.session_state.daily_revenue = 0.0
if 'net_profit' not in st.session_state:
    st.session_state.net_profit = 0.0
if 'total_profit' not in st.session_state:
    st.session_state.total_profit = 0.0
if 'pump_fillage' not in st.session_state:
    st.session_state.pump_fillage = 0.0
#endregion

#region SIDEBAR
#================================================================================
#                                SIDEBAR SLIDERS
#================================================================================
with st.sidebar:
    st.title("Well Operations Controls")
    st.caption("Adjust operating parameters:")
    
    #INJECTION CONTROLS
    with st.expander("1. Injection Controls", expanded=False):
        steam_toggle = st.radio("Steam Injector Switch:", ["ON", "OFF"], index =1, horizontal= True)
        injector_is_off = (steam_toggle == "OFF")

        steam_rate = st.slider("Steam Injection Rate (bbl/day)", 100, 1000, 450, 10, disabled = injector_is_off)
        steam_temp = st.slider("Surface Steam Temperature (K)", 500, 700, 600, 5, disabled = injector_is_off)
        steam_q = st.slider("Steam Quality (%)", 0.4, 1.0, 0.8, 0.05, disabled = injector_is_off)
        injection_duration = st.slider("Duration of Injection (days)", 5, 60, 21, 1, disabled = injector_is_off)

    #SOAKING CONTROLS
    with st.expander("2. Soaking Controls", expanded=False):
        soak_duration = st.slider("Duration of Soak (days)", 2, 14, 5, 1)

    #PRODUCTION CONTROLS
    with st.expander("3. Production (SRP) Controls", expanded=False):
        pump_toggle = st.radio("Pump Control Switch:", ["ON", "OFF"], index =1, horizontal= True)
        pump_is_off = (pump_toggle == "OFF")

        pump_spd = st.slider("Pump speed (SPM)", 2, 25, 8, 1, disabled = pump_is_off)

    #ECONOMICS CONTROLS
    with st.expander("Economics and Operational Defaults", expanded= False):
        eco_locked = st.checkbox(" Lock Configuration", value = False)

        steam_cost = st.slider("Steam Generation Cost (₹/ton)", 1000.00, 5000.00, 2500.00, 100.00, disabled=eco_locked)
        elec_cost = st.slider("Electricity Cost (₹/kWh)", 5, 30, 12, 1, disabled=eco_locked)
        oil_price = st.slider("Crude Oil Price (₹/bbl)", 2000.00, 12000.00, 6500.00, 100.00, disabled=eco_locked)
        cosr_max= st.slider("Maximum Allowable SOR (bbls/bblo)", 1.5, 8.0, 3.50, 0.1, disabled=eco_locked)
        min_eco_rate = st.slider("Minimum Rate of Oil Production (bbl/day)", 1, 10, 5, 1, disabled=eco_locked)
        if eco_locked:
            st.caption("*Configuration locked. Uncheck above to modify.*")

    #DESIGN CONTROLS
    with st.expander("Well Design Parameters", expanded=False):
        well_locked = st.checkbox("Lock Well Configuration", value=False)

        well_casing_diameter = st.slider("Well Casting Diameter (inches)", 2.375, 4.500, 2.875, 0.125, disabled=well_locked)
        depth = st.slider("Well Depth (m)", 500, 3000, 1500, 10, disabled=well_locked)

        if well_locked:
            st.caption("*Configuration locked. Uncheck above to modify.*")

    #STEP CONTROLS 
    step_button = st.button("Advance a day", type="primary")
#endregion

#region MASTER CLOCK AND FUNCTIONS
#================================================================================
#                           MASTER CLOCK AND FUNCTIONS
#================================================================================
if step_button:
    st.session_state.simulation_day += 1

current_day = st.session_state.simulation_day

if current_day == 0:
    st.session_state.current_stage = "Intializing..."

#============================STAGE 1: STEAM INJECTION============================
elif current_day <= injection_duration:
    st.session_state.current_stage = "Stage 1: Steam Injection"
    #Reservoir Temp
    if current_day == 1:
            st.session_state.current_reservoir_temp = surface_earth_temp + (depth * geothermal_gradient)
    #Daily Calcs
    t_bottomhole = steam_temp * (1 - (wellbore_loss_factor * depth))
    enthalpy = (water_specific_heat * t_bottomhole) + (steam_q * latent_heat_vap)
    daily_heat_injected = (steam_rate * 158.987) * enthalpy

    #steam chamber calc
    initial_radius = (well_casing_diameter * 0.0254) / 2.0
    steam_chamber_radius = initial_radius + (current_day * radial_expansion_rate)
    #changing vol and mass
    dynamic_volume = 3.14159 * (steam_chamber_radius ** 2) * res_thickness
    dynamic_rock_mass = dynamic_volume * rock_density
    #Update Reservoir T
    temp_increase = daily_heat_injected / (dynamic_rock_mass * res_heat_capacity)
    st.session_state.current_reservoir_temp += temp_increase
    if st.session_state.current_reservoir_temp > t_bottomhole:
            st.session_state.current_reservoir_temp = t_bottomhole
    #updating visocity
    baseline_temp = surface_earth_temp + (depth * geothermal_gradient)
    t_kelvin = st.session_state.current_reservoir_temp + 273.15
    t_ref_kelvin = baseline_temp + 273.15
    current_viscosity = base_oil_viscosity * m.exp(ea_over_r * ((1.0 / t_kelvin) - (1.0 / t_ref_kelvin)))
    if current_viscosity < 10.0:
        current_viscosity = 10.0
            
    st.session_state.current_viscosity = current_viscosity
    st.session_state.peak_reservoir_temp = st.session_state.current_reservoir_temp
    st.session_state.total_steam_injected = steam_rate * current_day
    st.session_state.radial_penetration = steam_chamber_radius

#================================STAGE 2: SOAKING================================
elif current_day <= (injection_duration + soak_duration):
    st.session_state.current_stage = "Stage 2: Soaking"
    #natural rock temp in surrounds
    baseline_temp = surface_earth_temp + (depth * geothermal_gradient)
        
    #ays of soaking
    days_soaking = current_day - injection_duration

    #calculate temp difference and them temp lossover time
    current_delta_t = st.session_state.current_reservoir_temp - baseline_temp
    temp_loss = current_delta_t * caprock_heat_loss_rate
        
    # Drop the reservoir temperature for today
    st.session_state.current_reservoir_temp -= temp_loss
        
    t_kelvin = st.session_state.current_reservoir_temp + 273.15
    t_ref_kelvin = baseline_temp + 273.15
    current_viscosity = base_oil_viscosity * m.exp(ea_over_r * ((1.0 / t_kelvin) - (1.0 / t_ref_kelvin)))
        
    # oil cant drop too low
    if current_viscosity < 10.0:
        current_viscosity = 10.0
            
    st.session_state.current_viscosity = current_viscosity
        
    # saving final temp for stage 3
    if current_day == (injection_duration + soak_duration):
        st.session_state.final_delta_t_0 = st.session_state.current_reservoir_temp - baseline_temp

#============================STAGE 3: SRP Production=============================
else:
    st.session_state.current_stage = "Stage 3: SRP Production"

    #Basic
    prod_day = current_day - (injection_duration + soak_duration)
    baseline_temp = surface_earth_temp + (depth * geothermal_gradient)
    delta_t_0 = st.session_state.get('final_delta_t_0', 50.0)

    #Cooling
    current_temp = baseline_temp + (delta_t_0 * m.exp(-k_cooling * prod_day))
    if current_temp < baseline_temp:
        current_temp = baseline_temp
    st.session_state.current_reservoir_temp = current_temp

    #Visocity
    t_kelvin = current_temp + 273.15
    t_ref_kelvin = baseline_temp + 273.15
    current_viscosity = base_oil_viscosity * m.exp(ea_over_r * ((1.0 / t_kelvin) - (1.0 / t_ref_kelvin)))
    if current_viscosity > base_oil_viscosity:
        current_viscosity = base_oil_viscosity
    st.session_state.current_viscosity = current_viscosity

    #daily oil rate
    daily_oil_rate = q_base * (base_oil_viscosity / current_viscosity)

    #DYNO CARD
    max_pump_capacity_per_day = pump_spd * 1440 * theoretical_displacement
    fillage_fraction = min(1.0, daily_oil_rate / max_pump_capacity_per_day)
    up_pos = np.linspace(0, 1, n)
    up_load =max_upstroke - 15*up_pos
    down_pos = np.linspace(0, 1, n)
    down_load = min_downstroke + 15*(1-down_pos)
    if fillage_fraction < 1.0:
            severity = 1.0 - fillage_fraction
            distortion = (severity * distortion_scaling_factor * np.sin(pi * (1 - down_pos)))
            down_load -= distortion
    st.session_state.daily_oil_rate = daily_oil_rate
    st.session_state.pump_fillage = fillage_fraction
    st.session_state.dyno_position = np.concatenate([up_pos, down_pos])
    st.session_state.dyno_load = np.concatenate([up_load, down_load])

    if st.session_state.pump_fillage < 0.75:
        st.warning(f"⚠️ **MECHANICAL WARNING:** Pump fillage has dropped to {st.session_state.pump_fillage * 100:.0f}%. Severe fluid pound detected. Risk of rod string failure.")
    
    st.session_state.daily_revenue = st.session_state.daily_oil_rate * oil_price_per_bbl
    st.session_state.net_profit = st.session_state.daily_revenue - daily_opex
    st.session_state.total_profit += st.session_state.net_profit
    # If the pump costs more to run than the oil it lifts is worth
    if st.session_state.net_profit <= 0:
        st.error(f"🛑 Daily revenue (₹{st.session_state.daily_revenue:.0f}) has fallen below daily operating cost (₹{daily_opex:.0f}). Halt production and initiate next steam cycle.")
    #region GRAPHS
#================================================================================
#                                   SIMULATION GRAPHS
#================================================================================
st.write("---")
st.markdown("## 📊 Simulation Graphs")




#endregion


#region DISPLAY
#================================================================================
#                                    DISPLAY
#================================================================================
st.header(f"Current Stage: {st.session_state.current_stage}")
#Row1: days and stage
col1, col2 = st.columns(2)
col1.metric("Simulation Day", st.session_state.simulation_day)

st.write("---")

# THERMODYNAMICS & RESERVOIR
st.markdown("#### Reservoir Physics")
col3, col4, col5 = st.columns(3)
col3.metric("Reservoir Temp (°C)", f"{st.session_state.current_reservoir_temp:.2f}")
col4.metric("Oil Viscosity (cP)", f"{st.session_state.current_viscosity:,.0f}")
col5.metric("Radial Heat Penetration (m)", f"{st.session_state.radial_penetration:.2f}")

st.write("")

# OPERATIONS & PRODUCTION
st.markdown("#### Surface Operations")
col6, col7, col8 = st.columns(3)
col6.metric("Total Steam Injected (bbls)", f"{st.session_state.total_steam_injected:,.0f}")
col7.metric("Daily Oil Rate (bbl/d)", f"{st.session_state.daily_oil_rate:.1f}")
col8.metric("Pump Fillage (%)", f"{st.session_state.pump_fillage * 100:.0f}%")

st.write("")

# MARKET ECONOMICS
st.markdown("#### Financials")
col9, col10, col11 = st.columns(3)
col9.metric("Daily Profit", f"₹{st.session_state.net_profit:,.2f}")
col10.metric("Total Profit", f"₹{st.session_state.total_profit:,.2f}")
 
#region GRAPHS
#================================================================================
#                                   SIMULATION GRAPHS
#================================================================================
st.write("---")
st.markdown("## 📊 Simulation Graphs")

def simulate_cycle(steam_rate, steam_temp, steam_q, injection_duration, soak_duration,
                    depth, prod_days):
    """
    Re-runs the full Injection -> Soak -> Production cycle as a standalone function,
    independent of session_state, so it can be called repeatedly for comparison plots
    without needing to click 'Advance a day'. Mirrors the physics in the Master Clock
    section above.
    """
    baseline_temp = surface_earth_temp + (depth * geothermal_gradient)
    reservoir_temp = baseline_temp
    total_days = injection_duration + soak_duration + prod_days

    days_arr = np.arange(0, total_days + 1)
    temp_arr = np.zeros_like(days_arr, dtype=float)
    visc_arr = np.zeros_like(days_arr, dtype=float)
    rate_arr = np.zeros_like(days_arr, dtype=float)

    t_bottomhole = steam_temp * (1 - wellbore_loss_factor * depth)
    enthalpy = (water_specific_heat * t_bottomhole) + (steam_q * latent_heat_vap)
    initial_radius = (well_casing_diameter * 0.0254) / 2.0
    final_delta_t0 = 0.0

    for i, day in enumerate(days_arr):
        if day == 0:
            reservoir_temp = baseline_temp
        elif day <= injection_duration:
            steam_chamber_radius = initial_radius + (day * radial_expansion_rate)
            dynamic_volume = 3.14159 * (steam_chamber_radius ** 2) * res_thickness
            dynamic_rock_mass = dynamic_volume * rock_density
            daily_heat_injected = (steam_rate * 158.987) * enthalpy
            temp_increase = daily_heat_injected / (dynamic_rock_mass * res_heat_capacity)
            reservoir_temp += temp_increase
            reservoir_temp = min(reservoir_temp, t_bottomhole)
        elif day <= (injection_duration + soak_duration):
            current_delta_t = reservoir_temp - baseline_temp
            temp_loss = current_delta_t * caprock_heat_loss_rate
            reservoir_temp -= temp_loss
            if day == (injection_duration + soak_duration):
                final_delta_t0 = reservoir_temp - baseline_temp
        else:
            prod_day = day - (injection_duration + soak_duration)
            reservoir_temp = baseline_temp + (final_delta_t0 * m.exp(-k_cooling * prod_day))
            reservoir_temp = max(reservoir_temp, baseline_temp)

        t_kelvin = reservoir_temp + 273.15
        t_ref_kelvin = baseline_temp + 273.15
        viscosity = base_oil_viscosity * m.exp(ea_over_r * ((1.0/t_kelvin) - (1.0/t_ref_kelvin)))
        viscosity = max(min(viscosity, base_oil_viscosity), 10.0)

        is_producing = day > (injection_duration + soak_duration)
        oil_rate = q_base * (base_oil_viscosity / viscosity) if is_producing else 0.0

        temp_arr[i], visc_arr[i], rate_arr[i] = reservoir_temp, viscosity, oil_rate

    return days_arr, temp_arr, visc_arr, rate_arr

prod_days_to_show = st.slider("Production days to simulate for graphs", 10, 120, 60, 5)
days_arr, temp_arr, visc_arr, rate_arr = simulate_cycle(
    steam_rate, steam_temp, steam_q, injection_duration, soak_duration, depth, prod_days_to_show
)


# 1.# Combined: Viscosity & Oil Production Rate vs Time
fig23, ax_visc = plt.subplots(figsize=(7, 4.5))

# Left axis: viscosity
color_visc = "#1565C0"
ax_visc.plot(days_arr, visc_arr, color=color_visc, label="Viscosity")
ax_visc.set_xlabel("Day")
ax_visc.set_ylabel("Viscosity (cP)", color=color_visc)
ax_visc.tick_params(axis='y', labelcolor=color_visc)

# Right axis: oil production rate, sharing the same x-axis
ax_rate = ax_visc.twinx()
color_rate = "#2E7D32"
ax_rate.plot(days_arr, rate_arr, color=color_rate, label="Oil Production Rate")
ax_rate.set_ylabel("Oil Rate (bbl/day)", color=color_rate)
ax_rate.tick_params(axis='y', labelcolor=color_rate)

# Combined legend (since each axis only knows its own line by default)
lines_1, labels_1 = ax_visc.get_legend_handles_labels()
lines_2, labels_2 = ax_rate.get_legend_handles_labels()
ax_visc.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")

ax_visc.set_title("Viscosity & Oil Production Rate vs Time")
ax_visc.grid(alpha=0.3)
fig23.tight_layout()
st.pyplot(fig23)

# 2. Production Rate for Different Steam Volumes
fig4, ax4 = plt.subplots(figsize=(7, 4))
for sr, color in zip([200, 450, 700, 1000], ["#90CAF9", "#42A5F5", "#1E88E5", "#0D47A1"]):
    d, t, v, r = simulate_cycle(sr, steam_temp, steam_q, injection_duration, soak_duration, depth, prod_days_to_show)
    ax4.plot(d, r, label=f"{sr} bbl/day steam", color=color)
ax4.set_xlabel("Day"); ax4.set_ylabel("Oil Rate (bbl/day)")
ax4.set_title("4. Production Rate for Different Steam Volumes")
ax4.legend(); ax4.grid(alpha=0.3)
st.pyplot(fig4)

# 3. Production Rate for Different Soak Times
fig5, ax5 = plt.subplots(figsize=(7, 4))
for sd, color in zip([2, 5, 8, 12], ["#FFCC80", "#FFA726", "#FB8C00", "#E65100"]):
    d, t, v, r = simulate_cycle(steam_rate, steam_temp, steam_q, injection_duration, sd, depth, prod_days_to_show)
    ax5.plot(d, r, label=f"{sd} days soak", color=color)
ax5.set_xlabel("Day"); ax5.set_ylabel("Oil Rate (bbl/day)")
ax5.set_title("5. Production Rate for Different Soak Times")
ax5.legend(); ax5.grid(alpha=0.3)
st.pyplot(fig5)

# 4. Dynamometer Card (live, from the actual simulation clock)
if st.session_state.current_stage == "Stage 3: SRP Production":
    fig6, ax6 = plt.subplots(figsize=(7, 5))
    ax6.plot(st.session_state.dyno_position, st.session_state.dyno_load, color="#6A1B9A")
    ax6.set_xlabel("Rod Position"); ax6.set_ylabel("Polished-Rod Load")
    ax6.set_title(f"6. Dynamometer Card (Fillage = {st.session_state.pump_fillage*100:.0f}%)")
    ax6.grid(alpha=0.3)
    st.pyplot(fig6)
else:
    st.info("Dynamometer card will appear once the well reaches Stage 3: SRP Production — click 'Advance a day' until then.") 
#endregion
