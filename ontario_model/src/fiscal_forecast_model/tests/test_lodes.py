import duckdb

from fiscal_forecast_model.ingest.lodes import aggregate_flows, load_ontario_blocks


def test_aggregate_flows(tmp_path):
    xw = tmp_path / "xw.csv"
    xw.write_text("tabblk2020,stplc\nA,0653896\nB,0653896\nC,0600000\n")
    main = tmp_path / "main.csv"
    main.write_text(
        "w_geocode,h_geocode,S000,SE03\n"
        "A,B,10,4\n"  # live & work in Ontario
        "A,C,5,1\n"  # inflow
        "C,A,7,2\n"  # outflow
        "C,C,100,50\n"  # unrelated
    )
    aux = tmp_path / "aux.csv"
    aux.write_text("w_geocode,h_geocode,S000,SE03\nB,ZZ,3,3\n")  # out-of-state resident

    con = duckdb.connect()
    assert load_ontario_blocks(con, str(xw), "0653896") == 2
    r = aggregate_flows(con, [str(main), str(aux)])
    assert r["jobs_in_ontario"] == 18
    assert r["employed_residents"] == 17
    assert r["live_and_work"] == 10
    assert r["jobs_high_wage"] == 8
    assert r["live_and_work_high_wage"] == 4
