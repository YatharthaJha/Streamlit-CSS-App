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
        pump_toggle = st.radio("Pump Switch:", ["ON", "OFF"], index =1, horizontal= True)
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
    with st.expander("Step controls", expanded = True):
        days_to_step = st.number_input("Days to step forward", min_value=1, max_value=30, value=1, step=1)
        step_button = st.button("Run Simulation Step", type="primary")
#endregion

#region MASTER CLOCK AND FUNCTIONS
#================================================================================
#                           MASTER CLOCK AND FUNCTIONS
#================================================================================
if step_button:
    st.session_state.simulation_day += days_to_step

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
    ### WAITING FOR ROLE 2 FUNCTIONS
#endregion

#region DISPLAY
#================================================================================
#                                    DISPLAY
#================================================================================
st.header(f"Current Stage: {st.session_state.current_stage}")
#Row1: days and stage
col1, col2 = st.columns(2)
col1.metric("Simulation Day", st.session_state.simulation_day)
col2.metric("Total Steam Injected (bbls)", f"{st.session_state.total_steam_injected:,.0f}")

st.write("")

#row2: dynamically changing temp and visocity
col3, col4 = st.columns(2)
col3.metric("Reservoir Temp (°C)", f"{st.session_state.current_reservoir_temp:.2f}")
col4.metric("Oil Viscosity (cP)", f"{st.session_state.current_viscosity:,.0f}")

st.write("")

#row2: total metrics
col5, col6 = st.columns(2)
col5.metric("Radial Heat Penetration (m)", f"{st.session_state.radial_penetration:.2f}")
col6.metric("Peak Reservoir Temperature (°C)", F"{st.session_state.peak_reservoir_temp:.2f}")

#endregion