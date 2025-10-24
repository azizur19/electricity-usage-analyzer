from dash import Dash, dcc, html
from dash.exceptions import PreventUpdate
from dash.dependencies import Output, Input, State
import plotly.express as px
from logger import *
from CT_calibration import * 

# ------------------- Dash App -------------------
app = Dash(__name__)

app.layout = html.Div([
    html.H2("ESP32 Live Sensor Data"),
    dcc.Checklist(
        id="auto-update-toggle",
        options=[{"label": " Auto Update", "value": "ON"}],
        value=["ON"],  # default checked
        inline=True,
        style={"marginBottom": "10px", "fontSize": 16}
    ),
    dcc.Graph(id="live-graph"),
    html.Div(id="on-off-time", style={"marginTop": 20, "fontSize": 18}),
    dcc.Interval(
        id="interval-component",
        interval=60*1000,
        n_intervals=0
    ),
    html.Div(
        id="show-report",
        children=[
            html.H4("Show Report"),
            html.Div([
                html.Label("Days:"),
                dcc.Input(id="report-days", type="number", min=0, value=0, step=1, style={"width": "80px", "marginRight": "16px"}),
                html.Label("Hours:"),
                dcc.Input(id="report-hours", type="number", min=0, value=0, step=1, style={"width": "80px", "marginRight": "16px"}),
                html.Label("Minutes:"),
                dcc.Input(id="report-minutes", type="number", min=0, value=0, step=1, style={"width": "80px", "marginRight": "16px"}),
                html.Button("Generate Report", id="generate-report", n_clicks=0, style={"marginLeft": "8px"})
            ], style={"display": "flex", "alignItems": "center", "gap": "8px"})
        ],
        style={"marginBottom": "12px", "padding": "6px", "border": "1px solid #ddd", "borderRadius": "6px"}
    )
])

# ------------------- Callbacks -------------------
@app.callback(
    [Output("live-graph", "figure"),
     Output("on-off-time", "children")],
    [
        Input("interval-component", "n_intervals"),
        Input("auto-update-toggle", "value"),
        Input("generate-report", "n_clicks")
    ],
    [
        State("report-days", "value"),
        State("report-hours", "value"),
        State("report-minutes", "value")
    ]
)

def update_graph(n, auto_update, gen_n_clicks, report_days, report_hours, report_minutes):
    # Decide whether this call is a manual "Generate Report" or a normal auto-update
    is_manual_report = (gen_n_clicks is not None and gen_n_clicks > 0)

    # If auto-update is OFF and this is NOT a manual report, pause updates
    if "ON" not in (auto_update or []) and not is_manual_report:
        print("Auto-update is OFF. Pausing updates.")
        raise PreventUpdate

    # Determine d/h/m to use for cropping the dataframe
    if is_manual_report:
        # convert inputs to integers (fall back to 0 if None)
        try:
            d = int(report_days or 0)
            h = int(report_hours or 0)
            m = int(report_minutes or 0)
        except Exception:
            d, h, m = 0, 0, 0
    else:
        # normal periodic update: do not crop (use full available data)
        d = h = m = None
# ------------------------------------------------------------------------------
    df = get_data()

    # If a manual report was requested, crop the dataframe to the last d/h/m window
    if d is not None:
        last_time = df["timestamp"].max()
        delta = pd.Timedelta(days=d, hours=h, minutes=m)
        crop_start = last_time - delta
        # Keep only rows within the requested window
        df = df[df["timestamp"] >= crop_start].reset_index(drop=True)
        start_time_24_h = crop_start
    else:
        last_time = df["timestamp"].max()
        start_time_24_h = last_time - pd.Timedelta(hours=24)
        # df = df[df["timestamp"] >= start_time_24_h].reset_index(drop=True)

    # Calculate time differences
    df["time_diff"] = df["timestamp"].diff().dt.total_seconds().fillna(0)

    # If gap > 5 minutes, treat it as 0 (power/WiFi outage)
    df.loc[df["time_diff"] > 300, "time_diff"] = 0

    # Determine Fridge ON/OFF
    df["Fridge_ON"] = df["value"] > 80

    # Compute ON/OFF durations
    total_on_hours = df.loc[df["Fridge_ON"], "time_diff"].sum() / 3600
    total_off_hours = df.loc[~df["Fridge_ON"], "time_diff"].sum() / 3600

    # Compute total available logged data
    total_data_hours = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).total_seconds() / 3600

        # --- NEW: Compute energy consumption ---
    # Current as average of current and previous value
    df["current"] = df["value"].rolling(2).mean()
    
    # Apply calibration to get actual current in Amps
    df["current_actual"] = df["current"].apply(get_current)
    
    # Instantaneous power in W
    df["power_W"] = df["current_actual"] * 210  # 210V approximation
    
    # Energy for each interval in Wh
    df["energy_Wh"] = df["power_W"] * (df["time_diff"] / 3600)
    
    # Only consider energy when fridge is ON
    df["energy_Wh_ON"] = df["energy_Wh"].where(df["Fridge_ON"], 0)
    
    # Total energy in kWh
    total_kwh = df["energy_Wh_ON"].sum() / 1000
    
    # Energy in last 24 hours (today usage)
    today_kwh = df.loc[df["timestamp"] >= start_time_24_h, "energy_Wh_ON"].sum() / 1000
    
    # Daily average usage (based on available data)
    num_days = total_data_hours / 24
    daily_avg_kwh = total_kwh / num_days if num_days > 0 else 0

    # Create scatter plot
    fig = px.scatter(
        df, 
        x="timestamp", 
        y="value",
        color="Fridge_ON",
        color_discrete_map={True: "green", False: "red"},
        title="Sensor Value vs Time (Scatter View)"
    )
    fig.update_layout(
        xaxis_title="Timestamp",
        yaxis_title="Sensor Value",
        legend_title="Fridge Status",
        xaxis=dict(range=[start_time_24_h, last_time+pd.Timedelta(hours=1.5)])  # horizontal zoom on last 24 hours
    )

    # Get last update timestamp
    last_update = df["timestamp"].max().strftime("%Y-%m-%d %H:%M:%S")

    # Display text
    on_off_text = (
        f"✅ Last update: {last_update}\n"
        f"✅ Total ON: {total_on_hours:.3f} hours\n"
        f"✅ Total OFF: {total_off_hours:.3f} hours\n"
        f"✅ Total available data: {total_data_hours:.3f} hours\n"
        f"⚡ Total Energy Usage: {total_kwh:.3f} kWh\n"
        f"⚡ Last 24 hour Usage: {today_kwh:.3f} kWh\n"
        f"⚡ Daily Average Usage: {daily_avg_kwh:.3f} kWh"
    )

    return fig, on_off_text


if __name__ == "__main__":
    app.run(debug=True)

