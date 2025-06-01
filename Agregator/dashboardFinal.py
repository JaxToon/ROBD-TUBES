
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import time
from streamlit_option_menu import option_menu
from neo4j import GraphDatabase
import json

# Fungsi ambil data dari MongoDB
def getDataMongoDB(
    uri,
    db_name,
    collection_name,
    query_type="find",
    query=None,
    projection=None,
    return_dataframe=True,
    show_time=True,
    use_index=True):

    client = MongoClient(uri)
    db = client[db_name]
    
    # Pilih collection berdasarkan apakah menggunakan index atau tidak
    if use_index:
        collection = db["transactionlogindex"]
        collection_label = "with index"
    else:
        collection = db[collection_name]
        collection_label = "without index"

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
        if use_index:
            st.success(f"MongoDB query '{query_type}' executed {collection_label} in {end - start:.4f} seconds")
        else:
            st.warning(f"MongoDB query '{query_type}' executed {collection_label} in {end - start:.4f} seconds")

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
    database="neo4j",
    optimized=True):
    
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
        optimization_label = "optimized" if optimized else "non-optimized"
        if optimized:
            st.success(f"Neo4j query executed ({optimization_label}) in {end - start:.4f} seconds")
        else:
            st.warning(f"Neo4j query executed ({optimization_label}) in {end - start:.4f} seconds")
    
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
        use_index = st.selectbox("Optimasi", ["With Index", "Without Index"])

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
                projection={"_id": 0} if query_type == "find" else None,
                use_index=(use_index == "With Index")
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
    
    # Optimization option
    st.write("#### Optimasi Query")
    optimization_option = st.selectbox(
        "Pilih Skenario",
        ["Optimized (dengan index & optimasi)", "Non-optimized (tanpa index & optimasi)"]
    )
    optimized = "Optimized" in optimization_option
    
    # Query section
    st.write("#### Cypher Query")
    
    # Predefined query examples based on optimization
    if optimized:
        default_query = """MATCH (f:Franchise)-[:HAS_EMPLOYEE]->(e:Employee)
WHERE f.id_cafe <= 5 
RETURN e.name, e.id_employee, f.name as franchise_name, f.id_cafe
LIMIT 100"""
    else:
        default_query = """MATCH (f:Franchise)-[:HAS_EMPLOYEE]->(e:Employee)
RETURN e.name, e.id_employee, f.name as franchise_name, f.id_cafe
LIMIT 20"""
    
    cypher_query = st.text_area(
        "Masukkan Cypher Query",
        height=200,
        value=default_query
    )

    parameters_input = st.text_area(
        "Parameters (JSON format, opsional)",
        height=68,
        placeholder='{"limit": 10, "cafe_id": 1}'
    )
    
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
                    show_time=show_time,
                    optimized=optimized
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
                    show_time=False,
                    optimized=True
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
                            show_time=False,
                            optimized=True
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
    
    # Scenario selection
    st.write("#### Pilih Skenario Optimasi")
    scenario = st.selectbox(
        "Skenario",
        ["Scenario 1: Tanpa Indexing & Optimasi", "Scenario 2: Dengan Indexing & Optimasi"]
    )
    
    use_optimization = "Scenario 2" in scenario
    
    # Predefined combined query examples
    st.write("#### Query Gabungan Tersedia")
    query_options = [
        "Analisis Penjualan per Franchise", 
        "Analisis Penjualan Minuman per Franchise",
        "Custom Query"
    ]
    
    selected_query = st.selectbox("Pilih Query Template", query_options)
    
    if selected_query == "Analisis Penjualan per Franchise":
        st.write("##### Query: Analisis penjualan dan informasi franchise")
        
        if use_optimization:
            mongo_query = [
            {
                '$unwind': '$product'
            }, {
                '$group': {
                    '_id': '$id_franchise', 
                    'total_sales': {
                        '$sum': '$product.quantity'
                    }, 
                    'transaction_ids': {
                        '$addToSet': '$id_transaction'
                    }
                }
            }, {
                '$project': {
                    'total_sales': 1, 
                    'transaction_count': {
                        '$size': '$transaction_ids'
                    }, 
                    'avg_sales': {
                        '$divide': [
                            '$total_sales', {
                                '$size': '$transaction_ids'
                            }
                        ]
                    }
                }
            }, {
                '$sort': {
                    '_id': 1
                }
            }
        ]
            neo4j_query = """
            MATCH (f:Franchise)-[:IS_LOCATED]->(d:Daerah)
            WHERE f.id_cafe IN $cafe_ids
            RETURN f.id_cafe as id_cafe, f.name, f.year, d.kota, d.kecamatan, d.nama_daerah
            """
        else:
            mongo_query = [
            {
                '$unwind': '$product'
            }, {
                '$group': {
                    '_id': '$id_franchise', 
                    'total_sales': {
                        '$sum': '$product.quantity'
                    }, 
                    'transaction_ids': {
                        '$addToSet': '$id_transaction'
                    }
                }
            }, {
                '$project': {
                    'total_sales': 1, 
                    'transaction_count': {
                        '$size': '$transaction_ids'
                    }, 
                    'avg_sales': {
                        '$divide': [
                            '$total_sales', {
                                '$size': '$transaction_ids'
                            }
                        ]
                    }
                }
            }, {
                '$sort': {
                    '_id': 1
                }
            }
        ]
            neo4j_query = """
            WITH [id IN $cafe_ids WHERE id IS NOT NULL] AS valid_ids
            MATCH (f:Franchise)-[:IS_LOCATED]->(d:Daerah)
            WHERE f.id_cafe IN valid_ids
            RETURN f.id_cafe AS id_cafe, f.name, f.year, d.kota, d.kecamatan, d.nama_daerah
            """
    
    elif selected_query == "Analisis Penjualan Minuman per Franchise":
        st.write("##### Query: Analisis penjualan minuman dengan detail produk, harga, dan total revenue per franchise")
        if use_optimization:
            mongo_query = [
                {
                    '$unwind': '$product'
                }, {
                    '$group': {
                        '_id': {
                            'id_franchise': '$id_franchise', 
                            'id_product': '$product.id_product', 
                            'product_name': '$product.name'
                        }, 
                        'total_quantity': {
                            '$sum': '$product.quantity'
                        }
                    }
                }, {
                    '$project': {
                        '_id': 0, 
                        'id_franchise': '$_id.id_franchise', 
                        'id_product': '$_id.id_product', 
                        'product_name': '$_id.product_name', 
                        'total_quantity': 1
                    }
                }, {
                    '$sort': {
                        'id_franchise': 1, 
                        'total_quantity': -1
                    }
                }
            ]
            neo4j_query = """
            MATCH (f:Franchise)-[:HAS_PRODUCT]->(p:Product) 
            WHERE f.id_cafe IN $franchise_ids
            RETURN f.id_cafe as id_franchise, f.name as franchise_name, f.year as year, 
                   p.id_product as id_product, p.category as category, p.price as price
            ORDER BY f.id_cafe
            """
        else:
            mongo_query = [
                {
                    '$unwind': '$product'
                }, {
                    '$group': {
                        '_id': {
                            'id_franchise': '$id_franchise', 
                            'id_product': '$product.id_product', 
                            'product_name': '$product.name'
                        }, 
                        'total_quantity': {
                            '$sum': '$product.quantity'
                        }
                    }
                }, {
                    '$project': {
                        '_id': 0, 
                        'id_franchise': '$_id.id_franchise', 
                        'id_product': '$_id.id_product', 
                        'product_name': '$_id.product_name', 
                        'total_quantity': 1
                    }
                }, {
                    '$sort': {
                        'id_franchise': 1, 
                        'total_quantity': -1
                    }
                }
            ]
            neo4j_query = """
            MATCH (f:Franchise)-[:HAS_PRODUCT]->(p:Product) 
            RETURN f.id_cafe as id_franchise, f.name as franchise_name, f.year as year, 
                   p.id_product as id_product, p.category as category, p.price as price
            ORDER BY f.id_cafe
            """

    else:  # Custom Query
        st.write("##### Custom Query")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**MongoDB Query (Aggregation Pipeline)**")
            mongo_query_input = st.text_area("MongoDB Query", height=150, 
                placeholder='[{"$match": {...}}, {"$group": {...}}]')
        with col2:
            st.write("**Neo4j Query (Cypher)**")
            neo4j_query_input = st.text_area("Neo4j Query", height=150,
                placeholder='MATCH (n) RETURN n LIMIT 10')
    
    # Execute combined query
    if st.button("🚀 Jalankan Query Gabungan", type="primary"):
        if selected_query == "Custom Query":
            try:
                mongo_query = eval(mongo_query_input) if mongo_query_input.strip() else []
                neo4j_query = neo4j_query_input.strip()
            except:
                st.error("Format query tidak valid!")
                return
        
        if not mongo_query or not neo4j_query:
            st.error("Kedua query harus diisi!")
            return
        
        try:
            col1, col2 = st.columns(2)
            
            # Execute MongoDB query
            with col1:
                st.write("### 📊 Hasil MongoDB")
                with st.spinner("Menjalankan query MongoDB..."):
                    mongo_result = getDataMongoDB(
                        uri="mongodb://localhost:27017/",
                        db_name="dbcafe",
                        collection_name="transactionlog",
                        query_type="aggregate",
                        query=mongo_query,
                        use_index=use_optimization
                    )
                
                if not mongo_result.empty:
                    st.dataframe(mongo_result, use_container_width=True)
                    
                    # Extract IDs for Neo4j query based on selected query type
                    if selected_query == "Analisis Penjualan per Franchise":
                        cafe_ids = mongo_result['_id'].tolist()
                        neo4j_params = {"cafe_ids": cafe_ids}
                    elif selected_query == "Analisis Penjualan Minuman per Franchise":
                        franchise_ids = mongo_result['id_franchise'].unique().tolist()
                        neo4j_params = {"franchise_ids": franchise_ids}
                    else:
                        neo4j_params = {}
                else:
                    st.warning("Tidak ada data dari MongoDB")
                    neo4j_params = {}
            
            # Execute Neo4j query
            with col2:
                st.write("### 🔗 Hasil Neo4j")
                if neo4j_params or selected_query == "Custom Query":
                    with st.spinner("Menjalankan query Neo4j..."):
                        neo4j_result = getDataNeo4j(
                            uri="bolt://localhost:7687",
                            username="neo4j",
                            password="jekialacarte",
                            query=neo4j_query,
                            parameters=neo4j_params,
                            optimized=use_optimization
                        )
                    
                    if not neo4j_result.empty:
                        st.dataframe(neo4j_result, use_container_width=True)
                    else:
                        st.warning("Tidak ada data dari Neo4j")
                else:
                    st.warning("Tidak dapat menjalankan Neo4j query - tidak ada parameter")
                    neo4j_result = pd.DataFrame()
            
            # Combine results if both have data
            if not mongo_result.empty and not neo4j_result.empty:
                st.write("---")
                st.write("### 🔄 Hasil Gabungan")
                
                if selected_query == "Analisis Penjualan per Franchise":
                    # Merge results on cafe ID
                    try:
                        combined = pd.merge(
                            mongo_result, 
                            neo4j_result, 
                            left_on='_id', 
                            right_on='id_cafe', 
                            how='left'
                        )
                        
                        st.write("#### Analisis Penjualan per Franchise dengan Lokasi")
                        if not combined.empty:
                            st.dataframe(combined, use_container_width=True)
                            
                            # Show summary
                            st.write("**Ringkasan:**")
                            st.write(f"- Jumlah franchise: {len(combined)}")
                            st.write(f"- Total penjualan semua franchise: {combined['total_sales'].sum()}")
                            st.write(f"- Rata-rata penjualan per franchise: {combined['total_sales'].mean():.2f}")
                            
                            # Show top cities
                            if 'kota' in combined.columns:
                                city_summary = combined.groupby('kota')['total_sales'].sum().sort_values(ascending=False)
                                st.write("**Penjualan per Kota:**")
                                for city, sales in city_summary.head().items():
                                    st.write(f"- {city}: {sales} items")
                        else:
                            st.warning("Tidak ada data yang dapat digabungkan.")
                    except Exception as e:
                        st.error(f"Error saat menggabungkan data franchise: {str(e)}")
                
                elif selected_query == "Analisis Penjualan Minuman per Franchise":
                    # Merge results on franchise ID and product ID
                    try:
                        combined = pd.merge(
                            mongo_result, 
                            neo4j_result, 
                            left_on=['id_franchise', 'id_product'], 
                            right_on=['id_franchise', 'id_product'], 
                            how='inner'
                        )
                        
                        if not combined.empty:
                            # Calculate total price per product and franchise
                            combined['total_revenue'] = combined['total_quantity'] * combined['price']
                            
                            st.write("#### Analisis Penjualan Minuman per Franchise dengan Revenue")
                            st.dataframe(combined, use_container_width=True)
                            
                            # Show comprehensive summary
                            st.write("**Ringkasan Detail:**")
                            st.write(f"- Jumlah record penjualan produk: {len(combined)}")
                            st.write(f"- Jumlah franchise: {combined['id_franchise'].nunique()}")
                            st.write(f"- Jumlah jenis produk: {combined['id_product'].nunique()}")
                            st.write(f"- Total quantity produk terjual: {combined['total_quantity'].sum():,}")
                            st.write(f"- Rata-rata revenue per produk: Rp {combined['total_revenue'].mean():,.2f}")
                            st.write(f"- Total revenue dalam satu tahun: Rp {combined['total_revenue'].sum():,.2f}")
                            
                            # Show top products by revenue
                            if 'product_name' in combined.columns:
                                product_revenue = combined.groupby('product_name')['total_revenue'].sum().sort_values(ascending=False)
                                st.write("**Top 5 Produk Berdasarkan Revenue:**")
                                for product, revenue in product_revenue.head().items():
                                    st.write(f"- {product}: Rp {revenue:,.2f}")
                            
                            # Show top franchises by revenue
                            franchise_revenue = combined.groupby(['id_franchise', 'franchise_name'])['total_revenue'].sum().sort_values(ascending=False)
                            st.write("**Top 5 Franchise Berdasarkan Revenue:**")
                            for (franchise_id, franchise_name), revenue in franchise_revenue.head().items():
                                st.write(f"- {franchise_name} (ID: {franchise_id}): Rp {revenue:,.2f}")
                            
                            # Show category analysis
                            if 'category' in combined.columns:
                                category_analysis = combined.groupby('category').agg({
                                    'total_quantity': 'sum',
                                    'total_revenue': 'sum',
                                    'id_product': 'nunique'
                                }).round(2)
                                st.write("**Analisis per Kategori:**")
                                st.dataframe(category_analysis, use_container_width=True)
                            
                            # Show franchise performance
                            franchise_performance = combined.groupby(['id_franchise', 'franchise_name', 'year']).agg({
                                'total_quantity': 'sum',
                                'total_revenue': 'sum',
                                'id_product': 'nunique'
                            }).round(2)
                            franchise_performance.columns = ['Total Quantity', 'Total Revenue', 'Unique Products']
                            st.write("**Performa per Franchise:**")
                            st.dataframe(franchise_performance, use_container_width=True)
                            
                        else:
                            st.warning("Tidak ada data yang dapat digabungkan.")
                    except Exception as e:
                        st.error(f"Error saat menggabungkan data minuman: {str(e)}")
                        import traceback
                        st.write("**Full error traceback:**")
                        st.code(traceback.format_exc())
                
                else:  # Custom query
                    st.write("#### Hasil Custom Query")
                    st.write("**Data MongoDB:**")
                    st.dataframe(mongo_result)
                    st.write("**Data Neo4j:**")
                    st.dataframe(neo4j_result)
                    st.info("Untuk custom query, silakan lakukan analisis manual pada kedua hasil di atas.")
            else:
                if mongo_result.empty:
                    st.warning("Tidak ada data dari MongoDB untuk digabungkan")
                if neo4j_result.empty:
                    st.warning("Tidak ada data dari Neo4j untuk digabungkan")
                    
        except Exception as e:
            st.error(f"Error saat menjalankan query gabungan: {str(e)}")
            import traceback
            st.write("**Full error traceback:**")
            st.code(traceback.format_exc())
    
        # Performance comparison
        st.write("---")
        st.write("#### 📈 Perbandingan Performa")

        st.info("Menjalankan perbandingan performa untuk kedua skenario...")
        
        # Sample query for comparison
        sample_mongo_query = [
            {
                '$unwind': '$product'
            }, {
                '$group': {
                    '_id': '$id_franchise', 
                    'total_sales': {
                        '$sum': '$product.quantity'
                    }, 
                    'transaction_ids': {
                        '$addToSet': '$id_transaction'
                    }
                }
            }, {
                '$project': {
                    'total_sales': 1, 
                    'transaction_count': {
                        '$size': '$transaction_ids'
                    }, 
                    'avg_sales': {
                        '$divide': [
                            '$total_sales', {
                                '$size': '$transaction_ids'
                            }
                        ]
                    }
                }
            }, {
                '$sort': {
                    '_id': 1
                }
            }
        ]
        
        sample_neo4j_query = """MATCH (f:Franchise)-[:IS_LOCATED]->(d:Daerah)
            RETURN f.id_cafe as id_cafe, f.name, f.year, d.kota, d.kecamatan, d.nama_daerah"""
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Scenario 1: Tanpa Optimasi**")
            start_time = time.time()
            
            # MongoDB without optimization
            mongo_result_1 = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="dbcafe", 
                collection_name="transactionlog",
                query_type="aggregate",
                query=sample_mongo_query,
                use_index=False,
                show_time=False
            )
            
            # Neo4j without optimization
            neo4j_result_1 = getDataNeo4j(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="jekialacarte",
                query=sample_neo4j_query,
                optimized=False,
                show_time=False
            )
            
            total_time_1 = time.time() - start_time
            st.warning(f"Total waktu: {total_time_1:.4f} seconds")
        
        with col2:
            st.write("**Scenario 2: Dengan Optimasi**")
            start_time = time.time()
            
            # MongoDB with optimization
            mongo_result_2 = getDataMongoDB(
                uri="mongodb://localhost:27017/",
                db_name="dbcafe",
                collection_name="transactionlog", 
                query_type="aggregate",
                query=sample_mongo_query,
                use_index=True,
                show_time=False
            )
            
            # Neo4j with optimization
            neo4j_result_2 = getDataNeo4j(
                uri="bolt://localhost:7687",
                username="neo4j", 
                password="jekialacarte",
                query=sample_neo4j_query + " // with optimization",
                optimized=True,
                show_time=False
            )
            
            total_time_2 = time.time() - start_time
            st.success(f"Total waktu: {total_time_2:.4f} seconds")
        
        # Show improvement
        if total_time_1 > 0:
            improvement = ((total_time_1 - total_time_2) / total_time_1) * 100
            st.write(f"### 🎯 Peningkatan Performa: {improvement:.1f}%")
            
            if improvement > 0:
                st.success(f"Scenario 2 lebih cepat {improvement:.1f}% dari Scenario 1")
            else:
                st.warning("Tidak ada peningkatan performa yang signifikan")

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
    2. Pilih optimasi: `With Index` atau `Without Index`
    3. Masukkan query dalam format Python dict atau list
    4. Klik tombol **Jalankan Query**
    5. Bandingkan performa kedua skenario
    """)
elif selected == "Neo4j":
    st.sidebar.markdown("""
    **Neo4j Query:**
    1. Pilih skenario optimasi
    2. Masukkan Cypher query (atau gunakan template)
    3. Tambahkan parameters jika diperlukan
    4. Klik tombol **Jalankan Cypher Query**
    5. Lihat perbedaan performa
    """)
else:  # Combine
    st.sidebar.markdown("""
    **Combine Data:**
    1. Pilih skenario optimasi
    2. Pilih template query atau buat custom
    3. Klik tombol **Jalankan Query Gabungan**
    4. Lihat hasil gabungan dari kedua database
    5. Bandingkan performa kedua skenario
    """)

st.sidebar.markdown("---")
st.sidebar.title("💡 Contoh Query")

if selected == "MongoDB":
    st.sidebar.write("""
    **Contoh Query MongoDB:**
    - **find**: `{"transaction_date": "2024-12-07","id_employee": 5,"product.quantity": 2,"order_quantity": { "$gt": 7 }}`
    - **aggregate**: `[{'$match': {'name': 'Jennifer Miller'}}, {'$group': {'_id': '$id_franchise'}}, {'$project': {'_id': 0, 'id_franchise': '$_id'}}]`
    """)
elif selected == "Neo4j":
    st.sidebar.write("""
    **Contoh Query Neo4j:**`MATCH (f:Franchise)-[:HAS_EMPLOYEE]->(e:Employee)
    WHERE f.id_cafe <= 5 
    RETURN e.name, e.id_employee, f.name as franchise_name, f.id_cafe
    LIMIT 100`
    """)

if selected == "Combine":
    st.sidebar.markdown("""
    **Query Gabungan Tersedia:**
    - **Pegawai Terbaik Ramadhan**: Analisis pegawai terbaik dengan detail franchise
    - **Penjualan per Franchise**: Gabungan data penjualan dan lokasi
    
    **Skenario Optimasi:**
    - **Scenario 1**: Tanpa index, query tidak terbatas
    - **Scenario 2**: Dengan index, query ter-optimasi
    """)

st.sidebar.markdown("---")
st.sidebar.title("👨‍💻 Developer")
st.sidebar.markdown("""
<b>Muhammad Zaki Nur Rahman</b><br>
📧 zaki.muhammad.mznr@gmail.com<br><br>
<b>Firgy Matannatikka</b><br>
📧 firgymatannatikkas@gmail.com
""", unsafe_allow_html=True)

# -------- Main Content Berdasarkan Selection --------
if selected == "MongoDB":
    mongodb_page()
elif selected == "Neo4j":
    neo4j_page()
elif selected == "Combine":
    combine_page()