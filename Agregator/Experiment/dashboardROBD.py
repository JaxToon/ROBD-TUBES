import streamlit as st
from pymongo import MongoClient
import pandas as pd
import time
from streamlit_option_menu import option_menu
from neo4j import GraphDatabase

# Fungsi ambil data dari MongoDB
def getDataMongoDB(
    uri,
    db_name,
    collection_name,
    query_type="find",
    query=None,
    projection=None,
    return_dataframe=True,
    show_time=True):

    client = MongoClient(uri)
    db = client[db_name]
    collection_index = db["transactionlogindex"]

    start_index = time.time()
    try:
        if query_type == "find":
            query = query or {}
            cursor = collection_index.find(query, projection)
            result = list(cursor)
        elif query_type == "aggregate":
            if not isinstance(query, list):
                raise ValueError("Aggregation query harus dalam bentuk list pipeline.")
            result = list(collection_index.aggregate(query))
        else:
            raise ValueError("query_type harus 'find' atau 'aggregate'")
    except Exception as e:
        st.error(f"Terjadi error saat query: {e}")
        result = []
    end_index = time.time()

    if show_time:
        st.success(f"Query '{query_type}' executed using index in {end_index - start_index:.4f} seconds")

    client.close()

    client = MongoClient(uri)
    db = client[db_name]
    collection = db[collection_name]

    start = time.time()
    try:
        if query_type == "find":
            query = query or {}
            cursor = collection.find(query, projection)
            result = list(cursor)
        elif query_type == "aggregate":
            if not isinstance(query, list):
                raise ValueError("Aggregation query harus dalam bentuk list pipeline.")
            result = list(collection.aggregate(query))
        else:
            raise ValueError("query_type harus 'find' atau 'aggregate'")
    except Exception as e:
        st.error(f"Terjadi error saat query: {e}")
        result = []
    end = time.time()

    if show_time:
        st.warning(f"Query '{query_type}' executed without index in {end - start:.4f} seconds")

    client.close()

    if return_dataframe:
        return pd.DataFrame(result)
    else:
        return result
    
def getDataNeo4j(
    uri,
    username,
    password,
    query,
    parameters=None,
    return_dataframe=True,
    show_time=True,
    database="neo4j"):
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    start = time.time()
    result = []
    
    try:
        with driver.session(database=database) as session:
            # Execute query
            response = session.run(query, parameters or {})
            
            # Convert records to list of dictionaries
            result = []
            for record in response:
                # Convert record to dictionary
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j node/relationship objects
                    if hasattr(value, '__dict__'):
                        if hasattr(value, 'items'):  # Node or Relationship
                            record_dict[key] = dict(value)
                        else:
                            record_dict[key] = str(value)
                    else:
                        record_dict[key] = value
                result.append(record_dict)
                
    except Exception as e:
        st.error(f"Terjadi error saat query Neo4j: {e}")
        result = []
    finally:
        driver.close()
    
    end = time.time()
    
    if show_time:
        st.success(f"Neo4j query executed in {end - start:.4f} seconds")
    
    if return_dataframe:
        return pd.DataFrame(result)
    else:
        return result

# Fungsi untuk page MongoDB
def mongodb_page():
    st.subheader("📊 Akses Data dari MongoDB")
    
    # -------- Main Area Input --------
    col1, col2 = st.columns(2)
    with col1:
        query_type = st.selectbox("Pilih Jenis Query", ["find", "aggregate"])
    with col2:
        st.write("") # spacing

    st.write("#### Daftar Kolom")
    try:
        client = MongoClient("mongodb://localhost:27017/")
        db = client["dbcafe"]
        collection = db["transactionlog"]
        sample_doc = collection.find_one()
        if sample_doc:
            st.write(", ".join(f"`{key}`" for key in sample_doc.keys()))
        else:
            st.warning("Koleksi tidak memiliki dokumen.")
        client.close()
    except Exception as e:
        st.error(f"Tidak dapat terhubung ke MongoDB: {e}")

    query_input = st.text_area(
        "Masukkan Query",
        height=200,
        placeholder='Contoh: {"name": "Michael Smith"} atau [{"$match": {"name": "Michael Smith"}}]'
    )

    run_query = st.button("Jalankan Query")

    # -------- Main Area Output --------
    if run_query:
        try:
            query = eval(query_input)

            df = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="dbcafe",
                collection_name="transactionlog",
                query_type=query_type,
                query=query,
                projection={"_id": 0} if query_type == "find" else None
            )
            st.write("### Hasil Query")
            if df.empty:
                st.warning("Tidak ada data ditemukan.")
            else:
                st.dataframe(df)

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses query: {e}")

# Fungsi untuk page Neo4j
def neo4j_page():
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "jekialacarte"
    
    # Query section
    st.write("#### Cypher Query")
    cypher_query = st.text_area(
        "Masukkan Cypher Query",
        height=150,
        placeholder="MATCH (n) RETURN n LIMIT 10",
        value="MATCH (n) RETURN n LIMIT 10"
    )

    parameters_input = ""
    
    # Options
    col1, col2 = st.columns(2)
    with col1:
        show_time = st.checkbox("Tampilkan waktu eksekusi", value=True)
    with col2:
        return_dataframe = st.checkbox("Return sebagai DataFrame", value=True)
    
    # Execute query button
    if st.button("🚀 Jalankan Cypher Query", type="primary"):
        if not cypher_query.strip():
            st.error("Query tidak boleh kosong!")
            return
            
        try:
            # Parse parameters if provided
            parameters = None
            if parameters_input.strip():
                import json
                try:
                    parameters = json.loads(parameters_input)
                except json.JSONDecodeError as e:
                    st.error(f"Format JSON parameters tidak valid: {e}")
                    return
            
            # Execute query using the Neo4j function
            with st.spinner("Menjalankan query Neo4j..."):
                result = getDataNeo4j(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password,
                    query=cypher_query,
                    parameters=parameters,
                    return_dataframe=return_dataframe,
                    show_time=show_time
                )
            
            # Display results
            if return_dataframe:
                if not result.empty:
                    st.write(f"**Hasil Query:** {len(result)} record(s)")
                    st.dataframe(result, use_container_width=True)
                    
                    # Show summary statistics for numeric columns
                    numeric_cols = result.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        st.write("**Statistik Numerik:**")
                        st.dataframe(result[numeric_cols].describe())
                else:
                    st.info("Query berhasil dijalankan tapi tidak ada data yang ditampilkan.")
            else:
                if result:
                    st.write(f"**Hasil Query:** {len(result)} record(s)")
                    st.json(result)
                else:
                    st.info("Query berhasil dijalankan tapi tidak ada data yang ditampilkan.")
                    
        except Exception as e:
            st.error(f"Error saat menjalankan query: {str(e)}")
    
    # Database info section
    st.write("---")
    st.write("#### ℹ️ Informasi Database")
    
    if st.button("📊 Cek Koneksi & Info Database"):
        try:
            with st.spinner("Mengecek koneksi ke Neo4j..."):
                # Test connection with simple query
                info_result = getDataNeo4j(
                    uri=neo4j_uri,
                    username=neo4j_user,
                    password=neo4j_password,
                    query="CALL db.labels() YIELD label RETURN label ORDER BY label",
                    show_time=False
                )
                
                if not info_result.empty:
                    st.success("✅ Koneksi ke Neo4j berhasil!")
                    
                    col1, col2 = st.columns(2)
                    
                    # Show available labels
                    with col1:
                        st.write("**Labels yang tersedia:**")
                        labels = info_result['label'].tolist()
                        for label in labels:
                            st.write(f"• {label}")
                    
                    # Get relationship types
                    with col2:
                        rel_result = getDataNeo4j(
                            uri=neo4j_uri,
                            username=neo4j_user,
                            password=neo4j_password,
                            query="CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
                            show_time=False
                        )
                        
                        if not rel_result.empty:
                            st.write("**Relationship Types:**")
                            rel_types = rel_result['relationshipType'].tolist()
                            for rel_type in rel_types:
                                st.write(f"• {rel_type}")
                else:
                    st.warning("Koneksi berhasil tapi tidak ada labels yang ditemukan.")
                    
        except Exception as e:
            st.error(f"❌ Gagal terhubung ke Neo4j: {str(e)}")
            st.write("Pastikan:")
            st.write("• Neo4j server sudah berjalan")
            st.write("• URI, username, dan password benar")
            st.write("• Port tidak diblokir firewall")

# Fungsi untuk page Combine
def combine_page():
    st.subheader("🔄 Kombinasi Data MongoDB & Neo4j")
    
    st.info("Page Combine sedang dalam pengembangan")
    
    # Placeholder untuk konten kombinasi
    st.write("#### Fitur yang akan tersedia:")
    st.write("- Menggabungkan data dari MongoDB dan Neo4j")
    st.write("- Analisis relasional antara data dokumen dan graph")
    st.write("- Visualisasi hubungan data")
    st.write("- Export hasil kombinasi")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("##### MongoDB Query")
        mongo_query = st.text_area("MongoDB Query", height=100)
    
    with col2:
        st.write("##### Neo4j Query") 
        neo4j_query = st.text_area("Cypher Query", height=100)
    
    if st.button("Kombinasikan Data"):
        st.warning("Fitur Combine belum diimplementasi. Silakan tambahkan logika untuk menggabungkan data dari kedua database.")

# ================= Streamlit App =================
st.set_page_config(layout="wide", page_title="Query Database Data Cafe")
st.title("Query Database Data Cafe")

# -------- Sidebar Navigation --------
with st.sidebar:
    selected = option_menu(
        menu_title="Data Source",
        options=["MongoDB", "Neo4j", "Combine"],
        icons=["database", "diagram-3", "layers"],
        menu_icon="server",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "orange", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#02ab21"},
        }
    )

# -------- Sidebar Petunjuk & Developer --------
st.sidebar.markdown("---")
st.sidebar.title("📌 Panduan Penggunaan")

if selected == "MongoDB":
    st.sidebar.markdown("""
    **MongoDB Query:**
    1. Pilih jenis query: `find` atau `aggregate`
    2. Masukkan query dalam format Python dict atau list
    3. Klik tombol **Jalankan Query**
    4. Hasil akan ditampilkan di bawah
    """)
elif selected == "Neo4j":
    st.sidebar.markdown("""
    **Neo4j Query:**
    1. Masukkan connection details
    2. Tulis Cypher query
    3. Klik tombol **Jalankan Cypher Query**
    4. Hasil akan ditampilkan dalam format tabel
    """)
else:  # Combine
    st.sidebar.markdown("""
    **Combine Data:**
    1. Masukkan query untuk MongoDB
    2. Masukkan query untuk Neo4j
    3. Klik tombol **Kombinasikan Data**
    4. Lihat hasil gabungan kedua database
    """)

st.sidebar.markdown("---")
st.sidebar.title("👨‍💻 Developer")
st.sidebar.markdown("""
<b>Muhammad Zaki Nur Rahman</b><br>
📧 zaki.muhammad.mznr@gmail.com<br><br>
<b>Firgy Matannatikka</b><br>
📧 firgy@gmail.com
""", unsafe_allow_html=True)

# -------- Main Content Berdasarkan Selection --------
if selected == "MongoDB":
    mongodb_page()
elif selected == "Neo4j":
    neo4j_page()
elif selected == "Combine":
    combine_page()


