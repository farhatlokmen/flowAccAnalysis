import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import numpy as np
import jinja2 
import os
from urllib.error import URLError

st.set_page_config(page_title="Flow Accumulation Analysis", page_icon="🌊")

st.markdown("# Flow Accumulation")
st.write(
    """This tool compares the designed flow calculations against the observed flow readings
    for selected irrigation valves corresponding to a user-specified period of time."""
)

try:
    pwd_container = st.empty()
    pwd_container.text_input("", type="password", placeholder = "Password", key="text_input")
    if (st.session_state.text_input != "2023"):
        st.info("Please enter correct password!")
    else:
        pwd_container.empty()
        st.success("You have successfully logged in !")
        uploaded_files = st.file_uploader("", accept_multiple_files=True) 
        if not(uploaded_files is not None and len(uploaded_files)==2):
            st.warning("Upload only the two files corresponding to designed and observed flow.")
        else:  
            idx_observed = 1
            if "acc" in uploaded_files[0].name:            
                idx_observed = 0
            idx_designed = 1 - idx_observed
            designedFlow_DF = pd.read_csv(uploaded_files[idx_designed])
            observedFlow_DF = pd.read_csv(uploaded_files[idx_observed], header=None)            
            autoMode = st.radio('Automatic Irrigation Mode',['Sequence','Parallel'])
            valvesID = designedFlow_DF["valve"]
            if autoMode == "Parallel":
                valvesID = np.unique(designedFlow_DF["Group"]) 
                valveNames = []
                GPM = []
                lat = []
                lon = []
                for valveID in valvesID:
                    valveNames.append(list(designedFlow_DF[designedFlow_DF["Group"]==valveID]["valve"])[0]) 
                    GPM.append(np.sum(designedFlow_DF[designedFlow_DF["Group"]==valveID]["GPM"]))
                    lat.append(list(designedFlow_DF[designedFlow_DF["Group"]==valveID]["lat"])[0])
                    lon.append(list(designedFlow_DF[designedFlow_DF["Group"]==valveID]["lon"])[0])
                designedFlow_DF = pd.DataFrame({'valve': valveNames,'GPM': GPM,'lat':lat,'lon':lon})                
            valvesID = designedFlow_DF["valve"] 
            version = st.radio('ICC System',['ICC','ICCpro'])   
            flowsensor_systemError = st.radio('Exclude days when flow sensor was not active',['yes','no'])          
            if version == 'ICCpro':
                observedFlow_DF.drop(observedFlow_DF.columns[[3,5]],axis=1,inplace=True)
                observedFlow_DF = observedFlow_DF[observedFlow_DF[2].notna()]
                observedFlow_DF = observedFlow_DF[observedFlow_DF[1].notna()]
                observedFlow_DF.drop(index=[1], inplace=True)
                observedFlow_DF.reset_index(drop=True, inplace=True)
                observedFlow_DF.columns = range(observedFlow_DF.columns.size)
                valves = st.multiselect("Choose Irrigation Valve(s)", list(valvesID), [])                 
                if not valves:
                    st.warning("Please select at least one irrigation valve.")
                else:                    
                    valveNames = []
                    dates = []
                    Flow = []
                    Time = []
                    totalFlow_observed = []
                    totalFlow_designed = []
                    errorP = []
                    for valve in valves:
                        for day in observedFlow_DF[observedFlow_DF[0]==valve][1]:
                            index_observed = observedFlow_DF[(observedFlow_DF[1]==day) & (observedFlow_DF[0]==valve)][3].index
                            index_designed = designedFlow_DF[designedFlow_DF["valve"]==valve]["GPM"].index
                            obsTF = float(observedFlow_DF.iat[index_observed[0], 2])
                            hours = int(observedFlow_DF.iloc[index_observed[0]][3][:2])
                            minutes = int(observedFlow_DF.iloc[index_observed[0]][3][3:5])                            
                            if ((hours*60+minutes) != 0) & (flowsensor_systemError == "no"):                                
                                time = hours*60+minutes
                                Time.append(time)
                                desTF = time*float(designedFlow_DF.iat[index_designed[0], 1])  
                                valveNames.append(valve)
                                dates.append(day)
                                totalFlow_designed.append(desTF) 
                                totalFlow_observed.append(obsTF)
                                errorP.append(np.round(100*((obsTF-desTF)/desTF),2)) 
                            elif ((hours*60+minutes) != 0) & (flowsensor_systemError == "yes"):
                                if (obsTF!=0):
                                    time = hours*60+minutes
                                    Time.append(time)
                                    desTF = time*float(designedFlow_DF.iat[index_designed[0], 1])  
                                    valveNames.append(valve)
                                    dates.append(day)
                                    totalFlow_designed.append(desTF) 
                                    totalFlow_observed.append(obsTF)
                                    errorP.append(np.round(100*((obsTF-desTF)/desTF),2)) 
                    df1 = pd.DataFrame({'valves': valveNames,
                                        'date': pd.to_datetime(dates),
                                        'Time':Time,
                                        'Flow_observed':totalFlow_observed,
                                        'Flow_designed':totalFlow_designed,
                                        'errorP':errorP})  
                    if len(df1)==0:
                        st.warning(" Flow sensor was not active during the specified period!")
                    elif len(df1)>=1: 
                        startDate = pd.to_datetime(st.date_input('Start Date', df1[df1['valves'] == valves[0]]['date'].iloc[0]))
                        endDate = pd.to_datetime(st.date_input('End Date', df1[df1['valves'] == valves[0]]['date'].iloc[-1]))
                        df1_filtered1 = df1[(df1['date'] >= startDate) & (df1['date'] < endDate)] 
                        avgErrorP = []
                        n_obs = []            
                        for valve in valves:  
                            avgErrorP.append(np.round(np.mean(df1_filtered1[df1_filtered1['valves'] == valve]['errorP']),2))
                            n_obs.append(len(df1_filtered1[(df1_filtered1['valves'] == valve)]['errorP']))                        
                        df2 = pd.DataFrame({'valve': valves,'avgErrorP':avgErrorP,'nb days':n_obs}) 
                        st.write(df2) 
                        st.write('Average error of all selected valves (%):', np.round(np.mean(avgErrorP), 2))
                        chart_lines = (
                        alt.Chart(df1_filtered1, title="")
                            .mark_line()
                            .encode(
                                x="date",
                                y=alt.Y("errorP", stack=None),
                                color="valves:N",
                            )
                        )
                        st.altair_chart(chart_lines, use_container_width=True)
                        selected_indices = [np.where(designedFlow_DF["valve"] == valve)[0][0] for valve in valves]                     
                        st.map(designedFlow_DF[['lat','lon']].iloc[selected_indices], zoom=12)
                        
                        # export options
                         
            elif version == 'ICC':
                valves = st.multiselect("Choose Irrigation Valve(s)", list(valvesID), [])                
                if not valves:
                    st.warning("Please select at least one irrigation valve.")
                else:
                    valveNames = []
                    dates = []
                    Flow = []
                    Time = []
                    totalFlow_observed = []
                    totalFlow_designed = []
                    errorP = []
                    for valve in valves:                          
                        for k in range(0,len(observedFlow_DF[observedFlow_DF[5]==valve][14]),2):
                            day = observedFlow_DF[observedFlow_DF[5]==valve].iat[k,14]
                            index_observed = observedFlow_DF[(observedFlow_DF[14]==day) & (observedFlow_DF[5]==valve)][18].index
                            index_designed = designedFlow_DF[designedFlow_DF["valve"]==valve]["GPM"].index                            
                            index_observed_flow = index_observed[0] 
                            index_observed_time = index_observed[1] 
                            hours = int(observedFlow_DF.iat[index_observed_time, 18][11:13])
                            minutes = int(observedFlow_DF.iat[index_observed_time, 18][14:16])
                            obsTF = 1000*float(observedFlow_DF.iat[index_observed_flow, 18])
                            st.write(observedFlow_DF)



                            
                            if ((hours*60+minutes) != 0) & (flowsensor_systemError == "no"):                                 
                                time = hours*60+minutes
                                Time.append(time)
                                desTF = time*float(designedFlow_DF.iat[index_designed[0], 1]) 
                                valveNames.append(valve)
                                dates.append(day)
                                totalFlow_designed.append(desTF) 
                                totalFlow_observed.append(obsTF)
                                errorP.append(np.round(100*((obsTF-desTF)/desTF),2)) 
                            elif ((hours*60+minutes) != 0) & (flowsensor_systemError == "yes") & (obsTF!=0):
                                time = hours*60+minutes
                                Time.append(time)
                                desTF = time*float(designedFlow_DF.iat[index_designed[0], 1]) 
                                valveNames.append(valve)
                                dates.append(day)
                                totalFlow_designed.append(desTF) 
                                totalFlow_observed.append(obsTF)
                                errorP.append(np.round(100*((obsTF-desTF)/desTF),2)) 
                    df1 = pd.DataFrame({'valves': valveNames,
                                        'date': pd.to_datetime(dates),
                                        'Time':Time,
                                        'Flow_observed':totalFlow_observed,
                                        'Flow_designed':totalFlow_designed,
                                        'errorP':errorP})    
                    if len(df1)==0:
                        st.warning(" Flow sensor was not active during the specified period!")
                    elif len(df1)>=1: 
                        startDate = pd.to_datetime(st.date_input('Start Date', df1[df1['valves'] == valves[0]]['date'].iloc[0]))
                        endDate = pd.to_datetime(st.date_input('End Date', df1[df1['valves'] == valves[0]]['date'].iloc[-1]))
                        df1_filtered1 = df1[(df1['date'] >= startDate) & (df1['date'] < endDate)] 
                        st.write(df1_filtered1)
                        
                        avgErrorP = []
                        n_obs = []            
                        for valve in valves:  
                            avgErrorP.append(np.round(np.mean(df1_filtered1[df1_filtered1['valves'] == valve]['errorP']),2))
                            n_obs.append(len(df1_filtered1[(df1_filtered1['valves'] == valve)]['errorP']))                        
                        df2 = pd.DataFrame({'valve': valves,'avgErrorP':avgErrorP,'nb days':n_obs}) 
                        st.write(df2) 
                        st.write('Average error of all selected valves (%):', np.round(np.mean(avgErrorP), 2))
                        chart_lines = (
                        alt.Chart(df1_filtered1, title="")
                            .mark_line()
                            .encode(
                                x="date",
                                y=alt.Y("errorP", stack=None),
                                color="valves:N",
                            )
                        )
                        st.altair_chart(chart_lines, use_container_width=True)
                        selected_indices = [np.where(designedFlow_DF["valve"] == valve)[0][0] for valve in valves]                     
                        st.map(designedFlow_DF[['lat','lon']].iloc[selected_indices], zoom=12)
                        
                        # export options
                                            

except URLError as e:
    st.error(
        """
        **Error Message: %s
    """
        % e.reason
    )

