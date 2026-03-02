build_lib_example(
  NAME bc_rsu_handover_trust_v2x_adaptive
  SOURCE_FILES bc_rsu_handover_trust_v2x_adaptive.cc
  LIBRARIES_TO_LINK ${libcore} ${libnetwork} ${libinternet} ${libmobility} ${libwifi} ${libapplications}
)
