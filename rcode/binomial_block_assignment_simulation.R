#'
#' 
#'  Code for simulating block assignment pools
#' 
#' 
#' 

set.seed(1234)
res <- list()
library(slider)
library(purrr)
ntrials <- 60
p_unexpected <- .2
trial_total <- ntrials*p_unexpected
unexpected_combinations <- safely(function(x){
  trials_categories <- rbinom(ntrials, 1, p_unexpected)
  total_unexp <- sum(trials_categories) 
  moving_sum <- slide_sum(trials_categories, before = 1, step = 1)
  if(total_unexp < trial_total | total_unexp > trial_total){
    print('P > .2 or P < .2')
    return(NULL)
  } else{
    if(sum(moving_sum==2)){
      print('Unexpected trials near each other')
      return(NULL)
    } else{
      return(trials_categories)
    }
  }
})

nruns <- 100000
res <- map(1:nruns, .f = unexpected_combinations)
mathing_trials <- list()
index <- 1
for(i in res){
  output <- i
  if(is.null(output$result)){
    next
  } else{
    mathing_trials[[index]] <-  output$result
    index <- index + 1
  }
}

final_df <- do.call(cbind, mathing_trials)

final_df_no_dups <- t(final_df[!duplicated(final_df),])
final_df_no_dups <- as.data.frame(final_df_no_dups[final_df_no_dups[, 1] != 1,])

nrow(final_df_no_dups)
rowSums(final_df_no_dups)

readr::write_csv(x = final_df_no_dups, file = '.csv')



