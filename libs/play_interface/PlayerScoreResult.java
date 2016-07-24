package net.picty.googleplayinterface;

import com.google.android.gms.common.api.Status;
import com.google.android.gms.common.api.PendingResult;
import com.google.android.gms.common.api.GoogleApiClient;
import com.google.android.gms.common.api.ResultCallback;
import com.google.android.gms.games.Games;
import com.google.android.gms.games.leaderboard.Leaderboards;
import com.google.android.gms.games.leaderboard.LeaderboardScore;
import com.google.android.gms.games.leaderboard.LeaderboardVariant;
import net.picty.googleplayinterface.PlayerScoreResultCallback;

//public abstract class PlayerScoreResult implements ResultCallback<Leaderboards.LoadPlayerScoreResult>{
//    public void loadScore(GoogleApiClient api, String leaderboardId, int span, int leaderboardCollection) {
//        PendingResult<Leaderboards.LoadPlayerScoreResult> pr = Games.Leaderboards.loadCurrentPlayerLeaderboardScore(api, leaderboardId, span, leaderboardCollection);
//        pr.setResultCallback(this);
//    }
//}

public class PlayerScoreResult implements ResultCallback<Leaderboards.LoadPlayerScoreResult> {
    public void loadScore(GoogleApiClient api, String leaderboardId, int span, 
                        int leaderboardCollection, PlayerScoreResultCallback cb) {
        PendingResult<Leaderboards.LoadPlayerScoreResult> pr = Games.Leaderboards.loadCurrentPlayerLeaderboardScore(api, leaderboardId, span, leaderboardCollection);
        pr.setResultCallback(this);
        _cb = cb;
    }
    public void onResult(Leaderboards.LoadPlayerScoreResult result)
    {
        if (result.getStatus().isSuccess())
        {
            long s;
            LeaderboardScore ls = result.getScore();
            if (ls != null)
                s = ls.getRawScore();
            else
                s = 0;
            _cb.onScore(s);
        }
        else
        {
            _cb.onScore(-1);
        }
    }
    PlayerScoreResultCallback _cb;
}
