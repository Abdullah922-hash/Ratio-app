import streamlit as st
import pandas as pd

print("Stock Ration App")

# --------- File Processing Helper ---------
def process_files(uploaded_files):
    data = {}
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        try:
            if file_name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(uploaded_file)
            else:
                try:
                    df = pd.read_csv(uploaded_file)
                except UnicodeDecodeError:
                    encodings = ['latin1', 'iso-8859-1', 'cp1252']
                    for encoding in encodings:
                        try:
                            uploaded_file.seek(0)
                            df = pd.read_csv(uploaded_file, encoding=encoding)
                            break
                        except:
                            continue
                    else:
                        st.error(f"Could not read file {file_name}")
                        continue

            # Clean column names
            df.columns = df.columns.str.strip()
            data[file_name] = df

        except Exception as e:
            st.error(f"Error processing {file_name}: {str(e)}")
            continue
    return data

# --------- Streamlit Setup ---------
st.set_page_config(page_title="CSV Report App", layout="wide")

if "files_data" not in st.session_state:
    st.session_state.files_data = {}

# --------- Navigation ---------
page = st.sidebar.radio("Navigation", ["Upload CSV/Excel", "See Report"])

# --------- Upload Page ---------
if page == "Upload CSV/Excel":
    st.title("Upload CSV or Excel Files")

    uploaded_files = st.file_uploader("Choose files", type=["csv", "xls", "xlsx"], accept_multiple_files=True)

    if uploaded_files:
        data = process_files(uploaded_files)
        if data:
            st.session_state.files_data = data
            st.success("Files processed and stored successfully!")

            for name, df in data.items():
                st.subheader(f"Preview: {name}")
                st.dataframe(df.head())

# --------- Report Page ---------
elif page == "See Report":
    st.title("Report Viewer")

    if not st.session_state.files_data:
        st.warning("Please upload at least one file on the 'Upload CSV/Excel' page.")
    else:
        selected_file = list(st.session_state.files_data.keys())[0]
        df = st.session_state.files_data[selected_file]

        required_cols = {"Item/Packs", "Color", "Sizes", "BeforeSell SOH", "SALES QTY", "SOH", "DaysInStore"}
        if not required_cols.issubset(df.columns):
            st.error(f"File `{selected_file}` is missing required columns: {required_cols - set(df.columns)}")
        else:
            item_list = df['Item/Packs'].dropna().unique()
            selected_item = st.selectbox("Select Item/Packs", ["All"] + sorted(item_list.tolist()))

            choose_options = st.multiselect("Choose", ["Item Names", "Color", "Sizes"])

            if not choose_options:
                st.warning("Please select at least one option in 'Choose'")
                st.stop()

            if selected_item == "All":
                filtered_df = df.copy()
            else:
                filtered_df = df[df["Item/Packs"] == selected_item]

            group_cols = []
            if "Item Names" in choose_options:
                group_cols.append("Item/Packs")
            if "Color" in choose_options:
                group_cols.append("Color")
            if "Sizes" in choose_options:
                group_cols.append("Sizes")

            if not group_cols:
                st.warning("Please select at least one grouping option.")
                st.stop()

            grouped = filtered_df.groupby(group_cols).agg({
                "BeforeSell SOH": "sum",
                "SALES QTY": "sum",
                "SOH": "sum"
            }).reset_index()

            total_before_sell = grouped["BeforeSell SOH"].sum()
            total_net_sales = grouped["SALES QTY"].sum()
            total_SOH = grouped["SOH"].sum()

            if total_before_sell != 0:
                grouped["% of BeforeSell"] = (grouped["BeforeSell SOH"] / total_before_sell * 100).round(2)
            else:
                grouped["% of BeforeSell"] = 0.00

            if total_net_sales != 0:
                grouped["% of SALES QTY"] = (grouped["SALES QTY"] / total_net_sales * 100).round(2)
            else:
                grouped["% of SALES QTY"] = 0.00

            if total_SOH != 0:
                grouped["% of SOH"] = (grouped["SOH"] / total_SOH * 100).round(2)
            else:
                grouped["% of SOH"] = 0.00

            avg_days_in_store = filtered_df["DaysInStore"].mean()

            grouped["Per Day Sale"] = grouped["SALES QTY"] / (avg_days_in_store if avg_days_in_store < 30 else 30)
            grouped["Per Day Sale"] = grouped["Per Day Sale"].replace([float("inf"), -float("inf")], 0).fillna(0)

            grouped["Stock Months"] = grouped.apply(
                lambda row: row["SOH"] / row["Per Day Sale"] / 30 if row["Per Day Sale"] != 0 else 0,
                axis=1
            )

            grouped["Per Day Sale"] = grouped["Per Day Sale"].round(1)
            grouped["Stock Months"] = grouped["Stock Months"].round(1)

            def get_status(months):
                if months <= 3:
                    return "Danger"
                elif 3 < months < 4:
                    return "Safe"
                else:
                    return "OverStocked"

            grouped["Status"] = grouped["Stock Months"].apply(get_status)

            # ➕ Total Row with New Metrics
            total_row = {col: 'Total' if i == 0 else '' for i, col in enumerate(group_cols)}
            total_row["BeforeSell SOH"] = round(total_before_sell, 1)
            total_row["SALES QTY"] = round(total_net_sales, 1)
            total_row["SOH"] = round(total_SOH, 1)

            total_row["% of BeforeSell"] = round((total_before_sell / total_before_sell * 100), 1) if total_before_sell else 0.0
            total_row["% of SALES QTY"] = round((total_net_sales / total_net_sales * 100), 1) if total_net_sales else 0.0
            total_row["% of SOH"] = round((total_SOH / total_SOH * 100), 1) if total_SOH else 0.0

            total_row["Per Day Sale"] = round(total_net_sales / (avg_days_in_store if avg_days_in_store < 30 else 30), 1)
            total_row["Stock Months"] = round(total_row["SOH"] / total_row["Per Day Sale"] / 30, 1) if total_row["Per Day Sale"] != 0 else 0.0
            total_row["Status"] = get_status(total_row["Stock Months"])

            grouped = pd.concat([grouped, pd.DataFrame([total_row])], ignore_index=True)

            # Format % columns
            grouped["% of BeforeSell"] = grouped["% of BeforeSell"].astype(float).round(1).astype(str) + '%'
            grouped["% of SALES QTY"] = grouped["% of SALES QTY"].astype(float).round(1).astype(str) + '%'
            grouped["% of SOH"] = grouped["% of SOH"].astype(float).round(1).astype(str) + '%'

            # Final column order
            display_cols = group_cols + [
                "BeforeSell SOH", "% of BeforeSell",
                "SALES QTY", "% of SALES QTY",
                "SOH", "% of SOH",
                "Per Day Sale", "Stock Months", "Status"
            ]
            grouped = grouped[display_cols]

            title = "Report for: All Items" if selected_item == "All" else f"Report for: {selected_item}"
            st.subheader(title)
            st.dataframe(grouped)
