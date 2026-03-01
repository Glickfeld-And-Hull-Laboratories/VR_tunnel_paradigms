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
unexpected_combinations <- safely(function(x){
  trials_categories <- rbinom(100, 1, .15)
  total_unexp <- sum(trials_categories) 
  moving_sum <- slide_sum(trials_categories, before = 1, step = 1)
  if(total_unexp < 15 | total_unexp > 15){
    print('P > .15 or P < .15')
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

res <- map(1:50000, .f = unexpected_combinations)
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
readr::write_csv(x = final_df_no_dups, file = '.csv')



