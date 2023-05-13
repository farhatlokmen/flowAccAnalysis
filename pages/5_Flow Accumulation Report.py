import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import numpy as np
import pdfkit
import jinja2 
import os
import tools
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

        #@st.cache(show_spinner=True, max_entries=1)
        uploaded_files = st.file_uploader("", accept_multiple_files=True) 
        if not(uploaded_files is not None and len(uploaded_files)==2):
            st.warning("Upload only the two files corresponding to designed and observed flow.")
        else:  
            idx_observed = 1
            if "acc" in uploaded_files[0].name:            
                idx_observed = 0
            idx_designed = 1 - idx_observed
            # Need to retain same file names to maintain alphabetic order
            designedFlow_DF = pd.read_csv(uploaded_files[idx_designed])
            observedFlow_DF = pd.read_csv(uploaded_files[idx_observed], header=None)
            
            version = st.radio('ICC System',['ICC','ICCpro'])   
            flowsensor_systemError = st.radio('Exclude days when flow sensor was not active',['yes','no'])          
            if version == 'ICCpro':
                # preprocess df
                observedFlow_DF.drop(observedFlow_DF.columns[[3,5]],axis=1,inplace=True)
                observedFlow_DF = observedFlow_DF[observedFlow_DF[2].notna()]
                observedFlow_DF = observedFlow_DF[observedFlow_DF[1].notna()]
                observedFlow_DF.drop(index=[1], inplace=True)
                observedFlow_DF.reset_index(drop=True, inplace=True)
                observedFlow_DF.columns = range(observedFlow_DF.columns.size)
                
                # prompt user to select valves to be examined
                valveNames_all = []
                for i in range(0,len(observedFlow_DF.iloc[:, 0]),2):
                    valveNames_all.append(observedFlow_DF.iloc[i, 0])        
                valves = st.multiselect("Choose Irrigation Valve(s)", list(np.unique(valveNames_all)), [])                
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
                            if ((hours*60+minutes) != 0) & (flowsensor_systemError == "no"): # Exclude out days with irrigation time being 0                                
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
                    elif len(df1)>=1: # Only do subsequent analysis, when flow sensor has been active for at least 1 day                    
                        # Prompt user to specify period # default date values to be set as 1st and last date in acc input file
                        startDate = pd.to_datetime(st.date_input('Start Date', df1[df1['valves'] == valves[0]]['date'].iloc[0]))
                        endDate = pd.to_datetime(st.date_input('End Date', df1[df1['valves'] == valves[0]]['date'].iloc[-1]))
                        df1_filtered1 = df1[(df1['date'] >= startDate) & (df1['date'] < endDate)] # Filter DataFrame based on used-defined dates
                        
                        # df summary 
                        avgErrorP = []
                        n_obs = []            
                        for valve in valves:  
                            avgErrorP.append(np.round(np.mean(df1_filtered1[df1_filtered1['valves'] == valve]['errorP']),2))
                            n_obs.append(len(df1_filtered1[(df1_filtered1['valves'] == valve)]['errorP']))                        
                        df2 = pd.DataFrame({'valve': valves,'avgErrorP':avgErrorP,'nb days':n_obs}) # Calculate avg error %
                        st.write(df2) 
                        
                        # display avg 
                        st.write('Average error of all selected valves (%):', np.round(np.mean(avgErrorP), 2))

                        # graph / chart
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

                        # GPS location valves 
                        selected_indices = [np.where(designedFlow_DF["valve"] == valve)[0][0] for valve in valves]                     
                        st.map(designedFlow_DF[['lat','lon']].iloc[selected_indices], zoom=12)
                        
                        # export options
                        pages_path = os.path.dirname(__file__)
                        app_path = os.path.dirname(pages_path)
                        
                        path=os.path.join(app_path,'./templates')
                        templateLoader = jinja2.FileSystemLoader(searchpath=path)
                        templateEnv = jinja2.Environment(loader=templateLoader)
                        TEMPLATE_FILE = "template.html"
                        template = templateEnv.get_template( TEMPLATE_FILE )

                        export_as_pdf = st.button("Export Report")

                        if export_as_pdf:
                            outputText = template.render(df=df2, timePeriod= 'from '+str(startDate)[:10]+' to '+str(endDate)[:10])
                            file_name = os.path.join(app_path,'reports', "report.html")
                            html_file = open(file_name, 'w', encoding='utf-8')
                            html_file.write(outputText)
                            html_file.close()

                            file_name = os.path.join(app_path,'reports', "report.html")
                            if os.path.isfile(file_name):         
                                #read html code to string
                                html_file = open(file_name, 'r', encoding='utf-8')
                                source_code = html_file.read() 
                                
                                # write the page break
                                source_code += '<div class="new-page"></div>'
                            else:
                                st.warning(f'{file_name} not found')

                            path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                            config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                            PDF_TARGET_FILE = os.path.join(app_path,'reports', "report.pdf")
                            pdfkit.from_string(source_code, PDF_TARGET_FILE, configuration=config) 
                            html_file.close()
                            st.success("Report successfully downloaded!")                     
                                            
                        
                        # Add logo

            elif version == 'ICC':
                valveNames_all = []
                for i in range(0,len(designedFlow_DF.iloc[:, 0]),2):
                    valveNames_all.append(designedFlow_DF.iloc[i, 0])        
                valves = st.multiselect("Choose Irrigation Valve(s)", list(np.unique(valveNames_all)), [])                
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
                            
                            index_observed_flow = index_observed[0] # Flow
                            index_observed_time = index_observed[1] # Time
                            hours = int(observedFlow_DF.iat[index_observed_time, 18][11:13])
                            minutes = int(observedFlow_DF.iat[index_observed_time, 18][14:16])
                            obs = float(observedFlow_DF.iat[index_observed_flow, 18])
                            if ((hours*60+minutes) != 0) & (flowsensor_systemError == "no"): # Exclude out days with irrigation time being 0                                
                                time = hours*60+minutes
                                Time.append(time)
                                desTF = time*float(designedFlow_DF.iat[index_designed[0], 1])                                
                                obsTF = time*obs
                                
                                valveNames.append(valve)
                                dates.append(day)
                                totalFlow_designed.append(desTF) 
                                totalFlow_observed.append(obsTF)
                                errorP.append(np.round(100*((obsTF-desTF)/desTF),2)) 
                            elif ((hours*60+minutes) != 0) & (flowsensor_systemError == "yes"):
                                if (obs!=0):
                                    time = hours*60+minutes
                                    Time.append(time)
                                    desTF = time*float(designedFlow_DF.iat[index_designed[0], 1])                                
                                    obsTF = time*obs

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
                    elif len(df1)>=1: # Only do subsequent analysis, when flow sensor has been active for at least 1 day
                        # Prompt user to specify period # default date values to be set as 1st and last date in acc input file
                        startDate = pd.to_datetime(st.date_input('Start Date', df1[df1['valves'] == valves[0]]['date'].iloc[0]))
                        endDate = pd.to_datetime(st.date_input('End Date', df1[df1['valves'] == valves[0]]['date'].iloc[-1]))
                        df1_filtered1 = df1[(df1['date'] >= startDate) & (df1['date'] < endDate)] # Filter DataFrame based on used-defined dates
                        
                        # df summary 
                        avgErrorP = []
                        n_obs = []            
                        for valve in valves:  
                            avgErrorP.append(np.round(np.mean(df1_filtered1[df1_filtered1['valves'] == valve]['errorP']),2))
                            n_obs.append(len(df1_filtered1[(df1_filtered1['valves'] == valve)]['errorP']))                        
                        df2 = pd.DataFrame({'valve': valves,'avgErrorP':avgErrorP,'nb days':n_obs}) # Calculate avg error %
                        st.write(df2) 
                        
                        # display avg 
                        st.write('Average error of all selected valves (%):', np.round(np.mean(avgErrorP), 2))

                        # graph / chart
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

                        # GPS location valves 
                        selected_indices = [np.where(designedFlow_DF["valve"] == valve)[0][0] for valve in valves]                     
                        st.map(designedFlow_DF[['lat','lon']].iloc[selected_indices], zoom=12)
                        
                        # export options
                        pages_path = os.path.dirname(__file__)
                        app_path = os.path.dirname(pages_path)
                        
                        path=os.path.join(app_path,'./templates')
                        templateLoader = jinja2.FileSystemLoader(searchpath=path)
                        templateEnv = jinja2.Environment(loader=templateLoader)
                        TEMPLATE_FILE = "template.html"
                        template = templateEnv.get_template( TEMPLATE_FILE )

                        export_as_pdf = st.button("Export Report")

                        if export_as_pdf:
                            outputText = template.render(df=df2, timePeriod= 'from '+str(startDate)[:10]+' to '+str(endDate)[:10])
                            file_name = os.path.join(app_path,'reports', "report.html")
                            html_file = open(file_name, 'w', encoding='utf-8')
                            html_file.write(outputText)
                            html_file.close()

                            file_name = os.path.join(app_path,'reports', "report.html")
                            if os.path.isfile(file_name):         
                                #read html code to string
                                html_file = open(file_name, 'r', encoding='utf-8')
                                source_code = html_file.read() 
                                
                                # write the page break
                                source_code += '<div class="new-page"></div>'
                            else:
                                st.warning(f'{file_name} not found')

                            path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
                            config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
                            PDF_TARGET_FILE = os.path.join(app_path,'reports', "report.pdf")
                            pdfkit.from_string(source_code, PDF_TARGET_FILE, configuration=config) 
                            html_file.close()
                            st.success("Report successfully downloaded!")                    

except URLError as e:
    st.error(
        """
        **Error Message: %s
    """
        % e.reason
    )

